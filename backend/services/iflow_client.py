"""
iFlow SDK 封装服务
提供流式对话处理、工具调用消息解析、连接管理、错误恢复等功能
支持系统提示词注入，用于定时任务意图识别
"""
import asyncio
import logging
import json
import re
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


# ==================== 系统提示词 ====================

# 定时任务意图识别系统提示词
SCHEDULE_TASK_SYSTEM_PROMPT = """
你是一个智能助手，具有创建定时任务的能力。

当用户表达想要创建定时任务/提醒/周期性任务时，请识别并返回特定格式的 JSON。

【识别关键词】
- "提醒我..."、"定时..."、"每天..."、"每周..."、"每月..."
- "每隔...分钟/小时..."、"周期性..."
- "到时间..."、"到时候..."

【返回格式】
如果用户意图是创建定时任务，请在响应的最后返回以下 JSON 格式：
```json
{"action": "create_task", "description": "用户的原始描述"}
```

【示例】
用户: "每天早上9点提醒我查看股票"
助手: 好的，我来帮你创建一个每天早上9点的提醒任务。
```json
{"action": "create_task", "description": "每天早上9点提醒我查看股票"}
```

用户: "每周一上午10点发送周报"
助手: 已为你创建每周一上午10点的定时任务。
```json
{"action": "create_task", "description": "每周一上午10点发送周报"}
```

用户: "每隔30分钟检查一次服务器状态"
助手: 好的，我将创建一个每隔30分钟的定时任务。
```json
{"action": "create_task", "description": "每隔30分钟检查一次服务器状态"}
```

【注意】
1. 只有当用户明确表达创建定时任务/提醒的意图时才返回 JSON
2. 普通对话不需要返回 JSON
3. JSON 必须放在响应的最后
4. description 字段保留用户的原始描述，不要修改
"""

# 前缀消息，用于注入系统提示词
SYSTEM_PROMPT_PREFIX = "[系统指令]\n" + SCHEDULE_TASK_SYSTEM_PROMPT + "\n[用户消息]\n"


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
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
        max_reconnect_attempts: int = 5,
        reconnect_base_delay: float = 1.0,
        health_check_interval: float = 60.0,
        session_id: Optional[str] = None,
    ):
        """
        初始化 iFlow 客户端服务
        
        Args:
            cwd: 工作目录，默认为 /root/.iflow-bot/workspace
            timeout: 超时时间（秒），默认使用配置中的超时时间
            max_reconnect_attempts: 最大重连尝试次数
            reconnect_base_delay: 重连基础延迟（秒）
            health_check_interval: 健康检查间隔（秒）
            session_id: iFlow 会话 ID，用于保持会话上下文
        """
        self.cwd = cwd or "/root/.iflow-bot/workspace"
        self.timeout = timeout or settings.IFLOW_TIMEOUT
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_base_delay = reconnect_base_delay
        self.health_check_interval = health_check_interval
        self.session_id = session_id
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
        使用 auto_start_process=True 让 iFlow SDK 自动管理进程
        支持自动重试
        """
        if self._is_connected and self._client:
            logger.debug("Already connected to iFlow service")
            return
        
        self._options = IFlowOptions(
            auto_start_process=True,  # 自动管理模式，让 SDK 启动和管理进程
            cwd=self.cwd,             # 工作目录
            timeout=self.timeout,
            session_id=self.session_id,  # 传入 session_id 保持会话上下文
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
                
                # 更新 session_id（首次连接时由服务器生成）
                # SDK 的 session_id 存储在 _session_id 属性中
                if hasattr(self._client, '_session_id') and self._client._session_id:
                    self.session_id = self._client._session_id
                    logger.info(f"Connected to iFlow service with cwd={self.cwd}, session_id={self.session_id}")
                else:
                    logger.info(f"Connected to iFlow service with cwd={self.cwd}")
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
            "cwd": self.cwd,
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
        enable_task_detection: bool = True,
    ) -> AsyncGenerator[ChatMessage, None]:
        """
        流式查询处理
        
        Args:
            message: 用户消息
            on_tool_call: 工具调用回调函数
            auto_reconnect: 是否在连接断开时自动重连
            enable_task_detection: 是否启用定时任务意图检测（注入系统提示词）
        
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
            # 如果启用任务检测，注入系统提示词
            actual_message = message
            if enable_task_detection:
                actual_message = SYSTEM_PROMPT_PREFIX + message
            
            # 发送消息
            await self._client.send_message(actual_message)
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


def extract_task_intent(response_text: str) -> Optional[Dict[str, Any]]:
    """
    从 AI 响应中提取定时任务意图
    
    Args:
        response_text: AI 响应文本
    
    Returns:
        Optional[Dict]: 如果检测到定时任务意图，返回 {"action": "create_task", "description": "..."}，否则返回 None
    """
    if not response_text:
        return None
    
    # 尝试提取 ```json ... ``` 块中的内容
    json_pattern = r'```json\s*([\s\S]*?)\s*```'
    matches = re.findall(json_pattern, response_text)
    
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, dict) and data.get("action") == "create_task":
                description = data.get("description", "")
                if description:
                    logger.info(f"Extracted task intent: {description}")
                    return data
        except json.JSONDecodeError:
            continue
    
    # 尝试提取 { ... } 块
    brace_pattern = r'\{[^{}]*"action"\s*:\s*"create_task"[^{}]*\}'
    matches = re.findall(brace_pattern, response_text)
    
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, dict) and data.get("action") == "create_task":
                description = data.get("description", "")
                if description:
                    logger.info(f"Extracted task intent: {description}")
                    return data
        except json.JSONDecodeError:
            continue
    
    return None


def remove_task_json_from_response(response_text: str) -> str:
    """
    从 AI 响应中移除定时任务 JSON 块，返回清理后的文本
    
    Args:
        response_text: AI 响应文本
    
    Returns:
        str: 清理后的文本
    """
    if not response_text:
        return response_text
    
    # 1. 移除 ```json ... ``` 块（包含 create_task 的）
    json_block_pattern = r'```json\s*\{[\s\S]*?"action"\s*:\s*"create_task"[\s\S]*?\}\s*```'
    cleaned = re.sub(json_block_pattern, '', response_text)
    
    # 2. 移除 ``` ... ``` 块（普通代码块中的 JSON）
    code_block_pattern = r'```\s*\{[\s\S]*?"action"\s*:\s*"create_task"[\s\S]*?\}\s*```'
    cleaned = re.sub(code_block_pattern, '', cleaned)
    
    # 3. 移除独立的 { ... } 块（单行或多行）
    # 处理多行 JSON
    multiline_json_pattern = r'\{[\s\S]*?"action"\s*:\s*"create_task"[\s\S]*?\}'
    cleaned = re.sub(multiline_json_pattern, '', cleaned)
    
    # 4. 移除纯 JSON 字符串（可能被转义）
    escaped_json_pattern = r'"\{[^"]*\\"action\\"\s*:\s*\\"create_task\\"[^"]*\}"'
    cleaned = re.sub(escaped_json_pattern, '', cleaned)
    
    # 5. 清理多余的空行和空格
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r'^\s+$', '', cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    
    return cleaned
