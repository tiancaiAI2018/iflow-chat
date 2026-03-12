"""
iFlow 业务逻辑处理器

订阅 EventBus 的 user_message 信号，调用 iFlow Client 进行 AI 对话，
并发射 ai_response/ai_complete/tool_call/plan 信号实现业务逻辑与输入输出的解耦。

使用 IFlowConnectionPool 管理连接，支持：
1. 同用户同会话复用连接
2. 同用户切换会话自动管理连接
3. 空闲超时自动清理
"""
import asyncio
import logging
from typing import Optional, Any, Dict
from dataclasses import dataclass, field
from datetime import datetime

from backend.services.event_bus import EventBus
from backend.services.iflow_client import IFlowClientService, MessageType
from backend.services.connection_pool import get_connection_pool

logger = logging.getLogger(__name__)


@dataclass
class ProcessorSession:
    """处理器会话信息（仅保存元数据，连接由连接池管理）"""
    user_id: int
    conversation_id: Optional[int] = None
    working_directory: str = "/root/.iflow-bot/workspace"
    created_at: datetime = field(default_factory=datetime.now)


class IFlowProcessor:
    """
    iFlow 业务逻辑处理器

    负责：
    1. 订阅 user_message 信号，接收用户输入
    2. 通过连接池管理用户的 iFlow Client 连接
    3. 调用 iFlow 进行 AI 对话
    4. 发射 ai_response、tool_call、plan 和 ai_complete 信号

    连接管理委托给 IFlowConnectionPool，支持：
    - 同用户同会话复用连接
    - 同用户切换会话自动管理连接
    - 空闲超时自动清理
    """

    def __init__(self):
        """初始化 iFlow 处理器"""
        # 用户会话映射：user_id -> ProcessorSession（仅保存元数据）
        self._sessions: Dict[int, ProcessorSession] = {}
        # 订阅者引用
        self._subscribers = []
        # 订阅信号
        self._subscribe_signals()

    def _subscribe_signals(self):
        """订阅 EventBus 信号"""
        @EventBus.on('user_message')
        def on_user_message(sender, **kwargs):
            # 创建异步任务处理
            asyncio.create_task(self._on_user_message(sender, **kwargs))
            return None

        # 保存订阅者引用以便后续取消
        self._subscribers = [on_user_message]
        logger.debug("IFlowProcessor subscribed to user_message signal")

    async def _on_user_message(self, sender: Optional[Any], **kwargs):
        """
        处理 user_message 信号

        通过连接池获取 iFlow Client 进行 AI 对话，并发射响应信号。

        Args:
            sender: 信号发送者
            **kwargs: 信号参数
                - user_id (int): 用户 ID
                - content (str): 消息内容
                - conversation_id (int, optional): 会话 ID
                - working_directory (str, optional): 工作目录
                - request_id (str, optional): 请求 ID，用于过滤消息
        """
        user_id = kwargs.get('user_id')
        content = kwargs.get('content', '')
        conversation_id = kwargs.get('conversation_id')
        working_directory = kwargs.get('working_directory', '/root/.iflow-bot/workspace')
        request_id = kwargs.get('request_id')  # 获取 request_id

        if not user_id or not content:
            logger.warning(f"Invalid user_message: user_id={user_id}, content_len={len(content)}")
            return

        logger.debug(f"Processing user_message: user_id={user_id}, request_id={request_id}, content={content[:50]}...")

        try:
            # 通过连接池获取或创建连接
            pool = get_connection_pool()
            iflow_client = await pool.get_connection(
                user_id=user_id,
                conversation_id=conversation_id or 0,
                working_directory=working_directory,
            )

            # 更新会话元数据
            self._sessions[user_id] = ProcessorSession(
                user_id=user_id,
                conversation_id=conversation_id,
                working_directory=working_directory,
            )

            # 调用 iFlow 进行对话
            full_response = []

            async for msg in iflow_client.query_stream(content):
                if msg.type == MessageType.TEXT:
                    # 文本消息 - 发射 ai_response 信号
                    if msg.content:
                        full_response.append(msg.content)

                    EventBus.emit(
                        'ai_response',
                        sender='iflow_processor',
                        user_id=user_id,
                        content=msg.content,
                        is_delta=msg.is_delta,
                        conversation_id=conversation_id,
                        request_id=request_id,  # 传递 request_id
                    )

                elif msg.type == MessageType.TOOL_CALL:
                    # 工具调用消息 - 发射 tool_call 信号
                    EventBus.emit(
                        'tool_call',
                        sender='iflow_processor',
                        user_id=user_id,
                        tool_id=msg.tool_id,
                        tool_name=msg.tool_name,
                        arguments=msg.tool_arguments,
                        status=msg.tool_status,
                        result=msg.tool_result,
                        error=msg.tool_error,
                        conversation_id=conversation_id,
                        request_id=request_id,
                    )

                elif msg.type == MessageType.PLAN:
                    # 任务计划消息 - 发射 plan 信号
                    EventBus.emit(
                        'plan',
                        sender='iflow_processor',
                        user_id=user_id,
                        entries=msg.plan_entries,
                        conversation_id=conversation_id,
                        request_id=request_id,
                    )

                elif msg.type == MessageType.TASK_FINISH:
                    # 任务完成 - 发射完成标记
                    EventBus.emit(
                        'ai_response',
                        sender='iflow_processor',
                        user_id=user_id,
                        content='',
                        is_delta=False,
                        conversation_id=conversation_id,
                        request_id=request_id,  # 传递 request_id
                    )

            # 发射 ai_complete 信号
            response_text = "".join(full_response)
            EventBus.emit(
                'ai_complete',
                sender='iflow_processor',
                user_id=user_id,
                content=response_text,
                conversation_id=conversation_id,
                request_id=request_id,  # 传递 request_id
            )

            logger.debug(f"Completed AI response for user {user_id}, request_id={request_id}, len={len(response_text)}")

        except Exception as e:
            logger.error(f"Error processing user_message: {e}")
            # 发射错误响应
            EventBus.emit(
                'ai_response',
                sender='iflow_processor',
                user_id=user_id,
                content=f"Error: {str(e)}",
                is_delta=False,
                conversation_id=conversation_id,
                metadata={'error': True},
            )
            EventBus.emit(
                'ai_complete',
                sender='iflow_processor',
                user_id=user_id,
                content='',
                conversation_id=conversation_id,
                metadata={'error': str(e)},
            )

    def get_session(self, user_id: int) -> Optional[ProcessorSession]:
        """
        获取用户会话元数据

        Args:
            user_id: 用户 ID

        Returns:
            Optional[ProcessorSession]: 用户会话元数据，不存在则返回 None
        """
        return self._sessions.get(user_id)

    async def close_user_session(self, user_id: int):
        """
        关闭指定用户的会话

        连接管理委托给连接池，这里只清理元数据。

        Args:
            user_id: 用户 ID
        """
        if user_id in self._sessions:
            del self._sessions[user_id]
            logger.debug(f"Cleared session metadata for user {user_id}")

    def disconnect(self):
        """
        断开信号订阅

        在不再需要接收消息时调用，取消所有信号订阅。
        """
        for subscriber in self._subscribers:
            try:
                EventBus.user_message.disconnect(subscriber)
            except Exception:
                pass

        self._subscribers.clear()
        logger.debug("IFlowProcessor disconnected from signals")

    async def close(self):
        """
        关闭所有资源

        断开信号订阅。连接由连接池管理，不需要在这里关闭。
        """
        self.disconnect()

        # 清理会话元数据
        self._sessions.clear()

        logger.info("IFlowProcessor closed all resources")

    async def __aenter__(self):
        """支持 async with 语法"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出时自动关闭"""
        await self.close()


# 全局处理器实例
_global_processor: Optional[IFlowProcessor] = None


def get_iflow_processor() -> IFlowProcessor:
    """
    获取全局 iFlow 处理器实例

    Returns:
        IFlowProcessor: 处理器实例
    """
    global _global_processor
    if _global_processor is None:
        _global_processor = IFlowProcessor()
    return _global_processor


async def close_iflow_processor() -> None:
    """
    关闭全局 iFlow 处理器
    """
    global _global_processor
    if _global_processor:
        await _global_processor.close()
        _global_processor = None