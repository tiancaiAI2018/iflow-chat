"""
iFlow SDK 封装服务
提供流式对话处理、工具调用消息解析、连接管理等功能
"""
import asyncio
import logging
from typing import AsyncGenerator, Optional, Callable, Any, Dict
from dataclasses import dataclass
from enum import Enum

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
    提供 WebSocket 连接管理、流式对话处理、工具调用消息解析
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """
        初始化 iFlow 客户端服务
        
        Args:
            url: WebSocket 地址，默认使用配置中的地址
            timeout: 超时时间（秒），默认使用配置中的超时时间
        """
        self.url = url or settings.IFLOW_WS_URL
        self.timeout = timeout or settings.IFLOW_TIMEOUT
        self._client: Optional[SDKClient] = None
        self._options: Optional[IFlowOptions] = None
        self._is_connected = False
    
    async def connect(self) -> None:
        """
        建立 WebSocket 连接
        """
        if self._is_connected and self._client:
            logger.debug("Already connected to iFlow service")
            return
        
        self._options = IFlowOptions(
            url=self.url,
            auto_start_process=False,  # 手动模式，连接已有服务
            timeout=self.timeout,
        )
        
        try:
            self._client = SDKClient(options=self._options)
            await self._client.__aenter__()
            self._is_connected = True
            logger.info(f"Connected to iFlow service: {self.url}")
        except Exception as e:
            logger.error(f"Failed to connect to iFlow service: {e}")
            self._is_connected = False
            raise
    
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
    
    async def reconnect(self) -> None:
        """
        重新连接
        """
        await self.disconnect()
        await self.connect()
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._is_connected and self._client is not None
    
    async def query_stream(
        self,
        message: str,
        on_tool_call: Optional[Callable[[ChatMessage], None]] = None,
    ) -> AsyncGenerator[ChatMessage, None]:
        """
        流式查询处理
        
        Args:
            message: 用户消息
            on_tool_call: 工具调用回调函数
        
        Yields:
            ChatMessage: 解析后的消息
        """
        if not self.is_connected:
            await self.connect()
        
        if not self._client:
            yield ChatMessage(
                type=MessageType.ERROR,
                content="Not connected to iFlow service"
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
                
                # 处理 ToolCallMessage（工具调用）
                elif isinstance(msg, ToolCallMessage):
                    tool_msg = self._parse_tool_call(msg)
                    
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
            
        except asyncio.TimeoutError:
            logger.error("Query timeout")
            yield ChatMessage(
                type=MessageType.ERROR,
                content="Query timeout, please try again"
            )
        except Exception as e:
            logger.error(f"Error during query: {e}")
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
            ToolCallStatus.COMPLETED: "completed",
            ToolCallStatus.FAILED: "failed",
        }
        
        return ChatMessage(
            type=MessageType.TOOL_CALL,
            tool_name=msg.tool_name,
            tool_arguments=msg.arguments,
            tool_status=status_map.get(msg.status, "unknown"),
            tool_result=msg.result if msg.status == ToolCallStatus.COMPLETED else None,
            tool_error=msg.error if msg.status == ToolCallStatus.FAILED else None,
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
