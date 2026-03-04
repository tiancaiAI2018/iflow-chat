"""
iFlow SDK 封装服务
提供流式对话处理、工具调用消息解析、连接管理、错误恢复等功能
"""
import asyncio
import logging
from typing import AsyncGenerator, Optional, Callable, Any, Dict
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

# iFlow SDK 导入
from iflow_sdk import (
    IFlowClient as SDKClient,
    IFlowOptions,
    AssistantMessage,
    ToolCallMessage,
    TaskFinishMessage,
    ToolCallStatus,
    StopReason,
)
from iflow_sdk.types import ToolResultMessage

from backend.config import settings

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型枚举"""
    TEXT = "text"              # 文本消息
    TOOL_CALL = "tool_call"    # 工具调用
    TASK_FINISH = "task_finish"  # 任务完成
    ERROR = "error"            # 错误消息


@dataclass
class ChatMessage:
    """聊天消息数据结构"""
    type: MessageType
    content: str = ""
    is_delta: bool = False      # 是否为增量消息
    is_finished: bool = False   # 是否完成
    
    # 工具调用相关
    tool_id: Optional[str] = None  # 工具调用 ID
    tool_name: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    tool_status: Optional[str] = None  # pending, in_progress, completed, failed
    tool_result: Optional[Any] = None
    tool_error: Optional[str] = None
    
    # 任务完成相关
    stop_reason: Optional[str] = None


class IFlowClientService:
    """
    iFlow SDK 封装服务
    提供 WebSocket 连接管理、流式对话处理、工具调用消息解析、自动重连
    包含服务可用性检测和错误恢复
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_reconnect_attempts: int = 5,
        reconnect_base_delay: float = 1.0,
        health_check_interval: float = 60.0,
    ):
        """
        初始化 iFlow 客户端服务
        
        Args:
            url: WebSocket 地址，默认使用配置中的地址
            timeout: 超时时间（秒），默认使用配置中的超时时间
            max_reconnect_attempts: 最大重连尝试次数
            reconnect_base_delay: 重连基础延迟（秒）
            health_check_interval: 健康检查间隔（秒）
        """
        self.url = url or settings.IFLOW_WS_URL
        self.timeout = timeout or settings.IFLOW_TIMEOUT
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_base_delay = reconnect_base_delay
        self.health_check_interval = health_check_interval
        self._client: Optional[SDKClient] = None
        self._options: Optional[IFlowOptions] = None
        self._is_connected = False
        self._connection_errors: list = []  # 记录连接错误历史
        self._last_connect_time: Optional[datetime] = None
        self._is_service_available = True  # 服务可用性标志
        self._consecutive_failures = 0  # 连续失败次数
        self._service_unavailable_threshold = 3  # 判定服务不可用的连续失败阈值
    
    async def connect(self) -> None:
        """
        建立 WebSocket 连接
        支持自动重试
        """
        if self._is_connected and self._client:
            logger.debug("Already connected to iFlow service")
            return
        
        self._options = IFlowOptions(
            url=self.url,
            auto_start_process=False,  # 手动模式，连接已有服务
            timeout=self.timeout,
        )
        
        last_error = None
        for attempt in range(self.max_reconnect_attempts):
            try:
                self._client = SDKClient(options=self._options)
                await self._client.__aenter__()
                self._is_connected = True
                self._last_connect_time = datetime.now()
                self._connection_errors = []  # 清空错误历史
                self._record_success()  # 记录成功连接
                logger.info(f"Connected to iFlow service: {self.url}")
                return
            except Exception as e:
                last_error = e
                self._connection_errors.append({
                    "time": datetime.now().isoformat(),
                    "error": str(e),
                    "attempt": attempt + 1,
                })
                self._record_failure(str(e))  # 记录失败
                
                if attempt < self.max_reconnect_attempts - 1:
                    delay = self.reconnect_base_delay * (2 ** attempt)  # 指数退避
                    logger.warning(
                        f"Connection attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
        
        # 所有尝试都失败
        logger.error(f"Failed to connect to iFlow service after {self.max_reconnect_attempts} attempts")
        self._is_connected = False
        raise ConnectionError(
            f"Failed to connect to iFlow service after {self.max_reconnect_attempts} attempts: {last_error}"
        )
    
    async def disconnect(self) -> None:
        """
        断开 WebSocket 连接
        """
        if self._client and self._is_connected:
            try:
                await self._client.__aexit__(None, None, None)
                logger.info("Disconnected from iFlow service")
            except Exception as e:
                logger.error(f"Error disconnecting from iFlow service: {e}")
            finally:
                self._client = None
                self._is_connected = False
    
    async def reconnect(self) -> bool:
        """
        重新连接
        
        Returns:
            bool: 是否重连成功
        """
        try:
            await self.disconnect()
            await self.connect()
            return True
        except Exception as e:
            logger.error(f"Reconnect failed: {e}")
            return False
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._is_connected and self._client is not None
    
    def get_connection_errors(self) -> list:
        """
        获取连接错误历史
        
        Returns:
            list: 错误历史列表
        """
        return self._connection_errors.copy()
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        获取连接状态信息
        
        Returns:
            Dict: 状态信息
        """
        return {
            "is_connected": self.is_connected,
            "is_service_available": self._is_service_available,
            "url": self.url,
            "last_connect_time": self._last_connect_time.isoformat() if self._last_connect_time else None,
            "error_count": len(self._connection_errors),
            "consecutive_failures": self._consecutive_failures,
            "last_error": self._connection_errors[-1] if self._connection_errors else None,
        }
    
    def _record_failure(self, error: str):
        """
        记录失败并更新服务可用性状态
        
        Args:
            error: 错误信息
        """
        self._consecutive_failures += 1
        
        if self._consecutive_failures >= self._service_unavailable_threshold:
            if self._is_service_available:
                logger.error(
                    f"iFlow service marked as unavailable after {self._consecutive_failures} consecutive failures"
                )
            self._is_service_available = False
    
    def _record_success(self):
        """记录成功并重置失败计数"""
        self._consecutive_failures = 0
        self._is_service_available = True
    
    @property
    def is_service_available(self) -> bool:
        """检查服务是否可用"""
        return self._is_service_available
    
    async def query_stream(
        self,
        message: str,
        on_tool_call: Optional[Callable[[ChatMessage], None]] = None,
        auto_reconnect: bool = True,
    ) -> AsyncGenerator[ChatMessage, None]:
        """
        流式查询处理
        
        Args:
            message: 用户消息
            on_tool_call: 工具调用回调函数
            auto_reconnect: 是否在连接断开时自动重连
        
        Yields:
            ChatMessage: 解析后的消息
        """
        if not self.is_connected:
            if auto_reconnect:
                try:
                    await self.connect()
                except Exception as e:
                    yield ChatMessage(
                        type=MessageType.ERROR,
                        content=f"Failed to connect to iFlow service: {str(e)}"
                    )
                    return
            else:
                yield ChatMessage(
                    type=MessageType.ERROR,
                    content="Not connected to iFlow service"
                )
                return
        
        if not self._client:
            yield ChatMessage(
                type=MessageType.ERROR,
                content="iFlow client not initialized"
            )
            return
        
        try:
            # 发送消息
            await self._client.send_message(message)
            logger.debug(f"Sent message: {message[:50]}...")
            
            # 接收并处理消息
            async for msg in self._client.receive_messages():
                # 处理 AssistantMessage（文本消息）
                if isinstance(msg, AssistantMessage):
                    yield ChatMessage(
                        type=MessageType.TEXT,
                        content=msg.chunk.text,
                        is_delta=True,
                        is_finished=False,
                    )
                
                # 处理 ToolCallMessage（工具调用开始）
                elif isinstance(msg, ToolCallMessage):
                    tool_msg = self._parse_tool_call(msg)
                    
                    # 调用回调
                    if on_tool_call:
                        on_tool_call(tool_msg)
                    
                    yield tool_msg
                
                # 处理 ToolResultMessage（工具调用结果/更新）
                elif isinstance(msg, ToolResultMessage):
                    tool_msg = self._parse_tool_result(msg)
                    
                    # 调用回调
                    if on_tool_call:
                        on_tool_call(tool_msg)
                    
                    yield tool_msg
                
                # 处理 TaskFinishMessage（任务完成）
                elif isinstance(msg, TaskFinishMessage):
                    yield ChatMessage(
                        type=MessageType.TASK_FINISH,
                        is_finished=True,
                        stop_reason=msg.stop_reason.value if msg.stop_reason else None,
                    )
                    break  # 结束消息循环
            
            # 发送完成标记
            yield ChatMessage(
                type=MessageType.TEXT,
                content="",
                is_delta=False,
                is_finished=True,
            )
            
            # 记录查询成功
            self._record_success()
            
        except asyncio.TimeoutError:
            logger.error("Query timeout")
            self._record_failure("Query timeout")
            yield ChatMessage(
                type=MessageType.ERROR,
                content="Query timeout, please try again"
            )
        except ConnectionError as e:
            logger.error(f"Connection error during query: {e}")
            self._is_connected = False
            self._record_failure(str(e))
            self._connection_errors.append({
                "time": datetime.now().isoformat(),
                "error": str(e),
                "type": "query_connection_error",
            })
            yield ChatMessage(
                type=MessageType.ERROR,
                content=f"Connection lost: {str(e)}. Please try again."
            )
        except Exception as e:
            logger.error(f"Error during query: {e}")
            # 检查是否是连接相关问题
            if "connection" in str(e).lower() or "websocket" in str(e).lower():
                self._is_connected = False
                self._record_failure(str(e))
                self._connection_errors.append({
                    "time": datetime.now().isoformat(),
                    "error": str(e),
                    "type": "query_error",
                })
            else:
                self._record_failure(str(e))
            yield ChatMessage(
                type=MessageType.ERROR,
                content=f"Error: {str(e)}"
            )
    
    def _parse_tool_call(self, msg: ToolCallMessage) -> ChatMessage:
        """
        解析工具调用消息
        
        Args:
            msg: ToolCallMessage 消息
        
        Returns:
            ChatMessage: 解析后的消息
        """
        status_map = {
            ToolCallStatus.PENDING: "pending",
            ToolCallStatus.IN_PROGRESS: "in_progress",
            ToolCallStatus.RUNNING: "in_progress",  # RUNNING 是 IN_PROGRESS 的别名
            ToolCallStatus.COMPLETED: "completed",
            ToolCallStatus.FAILED: "failed",
        }
        
        # 获取工具参数（SDK 使用 args 字段）
        tool_args = getattr(msg, 'args', None) or {}
        
        # 获取结果（从 content.markdown 字段提取）
        tool_result = None
        tool_error = None
        if hasattr(msg, 'content') and msg.content:
            content = msg.content
            # ToolCallContent 有 markdown 字段存储结果
            if hasattr(content, 'markdown') and content.markdown:
                tool_result = content.markdown
            # 检查是否有其他类型的错误信息
            if hasattr(content, 'error'):
                tool_error = content.error
        
        # 获取工具名称和 ID
        tool_name = msg.tool_name or msg.label or "unknown"
        tool_id = msg.id or f"{tool_name}-{hash(str(tool_args))}"
        
        # 日志记录，便于调试
        logger.debug(f"ToolCall: id={tool_id}, name={tool_name}, status={msg.status}, args={list(tool_args.keys()) if tool_args else []}, result_len={len(tool_result) if tool_result else 0}")
        
        return ChatMessage(
            type=MessageType.TOOL_CALL,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_arguments=tool_args,
            tool_status=status_map.get(msg.status, "in_progress"),
            tool_result=tool_result,
            tool_error=tool_error,
        )
    
    def _parse_tool_result(self, msg: ToolResultMessage) -> ChatMessage:
        """
        解析工具结果消息
        
        Args:
            msg: ToolResultMessage 消息
        
        Returns:
            ChatMessage: 解析后的消息
        """
        status_map = {
            ToolCallStatus.PENDING: "pending",
            ToolCallStatus.IN_PROGRESS: "in_progress",
            ToolCallStatus.RUNNING: "in_progress",
            ToolCallStatus.COMPLETED: "completed",
            ToolCallStatus.FAILED: "failed",
        }
        
        # ToolResultMessage 中 args 和 content 都有值
        tool_args = getattr(msg, 'args', None) or {}
        
        # 获取结果（从 content.markdown 字段提取）
        tool_result = None
        tool_error = None
        if hasattr(msg, 'content') and msg.content:
            content = msg.content
            if hasattr(content, 'markdown') and content.markdown:
                tool_result = content.markdown
            if hasattr(content, 'error'):
                tool_error = content.error
        
        # 获取工具名称和 ID
        tool_name = msg.tool_name or "unknown"
        tool_id = msg.id
        
        # 日志记录
        logger.debug(f"ToolResult: id={tool_id}, name={tool_name}, status={msg.status}, args_keys={list(tool_args.keys()) if tool_args else []}, result_len={len(tool_result) if tool_result else 0}")
        
        return ChatMessage(
            type=MessageType.TOOL_CALL,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_arguments=tool_args,
            tool_status=status_map.get(msg.status, "in_progress"),
            tool_result=tool_result,
            tool_error=tool_error,
        )
    
    async def query(self, message: str) -> str:
        """
        同步查询（返回完整响应）
        
        Args:
            message: 用户消息
        
        Returns:
            str: 完整响应文本
        """
        full_response = []
        
        async for msg in self.query_stream(message):
            if msg.type == MessageType.TEXT and msg.content:
                full_response.append(msg.content)
            elif msg.type == MessageType.ERROR:
                raise Exception(msg.content)
        
        return "".join(full_response)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()


# 全局客户端实例（可选，用于单例模式）
_global_client: Optional[IFlowClientService] = None


async def get_iflow_client() -> IFlowClientService:
    """
    获取全局 iFlow 客户端实例
    
    Returns:
        IFlowClientService: 客户端实例
    """
    global _global_client
    if _global_client is None:
        _global_client = IFlowClientService()
    return _global_client


async def close_iflow_client() -> None:
    """
    关闭全局 iFlow 客户端
    """
    global _global_client
    if _global_client:
        await _global_client.disconnect()
        _global_client = None
