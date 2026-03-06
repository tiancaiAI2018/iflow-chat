"""
iFlow 业务逻辑处理器

订阅 EventBus 的 user_message 信号，调用 iFlow Client 进行 AI 对话，
并发射 ai_response/ai_complete 信号实现业务逻辑与输入输出的解耦。
"""
import asyncio
import logging
from typing import Optional, Any, Dict
from dataclasses import dataclass, field
from datetime import datetime

from backend.services.event_bus import EventBus
from backend.services.iflow_client import IFlowClientService, MessageType

logger = logging.getLogger(__name__)


@dataclass
class ProcessorSession:
    """处理器会话信息"""
    user_id: int
    conversation_id: Optional[int] = None
    iflow_client: Optional[IFlowClientService] = None
    working_directory: str = "/root/.iflow-bot/workspace"
    created_at: datetime = field(default_factory=datetime.now)


class IFlowProcessor:
    """
    iFlow 业务逻辑处理器

    负责：
    1. 订阅 user_message 信号，接收用户输入
    2. 管理用户的 iFlow Client 连接
    3. 调用 iFlow 进行 AI 对话
    4. 发射 ai_response 和 ai_complete 信号

    使用示例：
        processor = IFlowProcessor()

        # 处理器会自动订阅信号并处理消息

        # 断开连接时
        processor.disconnect()
    """

    def __init__(self):
        """初始化 iFlow 处理器"""
        # 用户会话映射：user_id -> ProcessorSession
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

        调用 iFlow Client 进行 AI 对话，并发射响应信号。

        Args:
            sender: 信号发送者
            **kwargs: 信号参数
                - user_id (int): 用户 ID
                - content (str): 消息内容
                - conversation_id (int, optional): 会话 ID
                - working_directory (str, optional): 工作目录
        """
        user_id = kwargs.get('user_id')
        content = kwargs.get('content', '')
        conversation_id = kwargs.get('conversation_id')
        working_directory = kwargs.get('working_directory', '/root/.iflow-bot/workspace')

        if not user_id or not content:
            logger.warning(f"Invalid user_message: user_id={user_id}, content_len={len(content)}")
            return

        logger.debug(f"Processing user_message: user_id={user_id}, content={content[:50]}...")

        try:
            # 获取或创建用户会话
            session = await self._get_or_create_session(
                user_id=user_id,
                conversation_id=conversation_id,
                working_directory=working_directory,
            )

            # 调用 iFlow 进行对话
            full_response = []

            async for msg in session.iflow_client.query_stream(content):
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
                    )

            # 发射 ai_complete 信号
            response_text = "".join(full_response)
            EventBus.emit(
                'ai_complete',
                sender='iflow_processor',
                user_id=user_id,
                content=response_text,
                conversation_id=conversation_id,
            )

            logger.debug(f"Completed AI response for user {user_id}, len={len(response_text)}")

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

    async def _get_or_create_session(
        self,
        user_id: int,
        conversation_id: Optional[int] = None,
        working_directory: str = "/root/.iflow-bot/workspace",
    ) -> ProcessorSession:
        """
        获取或创建用户会话

        如果会话不存在或工作目录发生变化，创建新的 iFlow Client。

        Args:
            user_id: 用户 ID
            conversation_id: 会话 ID
            working_directory: 工作目录

        Returns:
            ProcessorSession: 用户会话
        """
        # 检查是否需要重新创建会话
        if user_id in self._sessions:
            session = self._sessions[user_id]
            # 如果工作目录没变，重用现有会话
            if session.working_directory == working_directory and session.iflow_client and session.iflow_client.is_connected:
                # 更新会话 ID
                if conversation_id is not None:
                    session.conversation_id = conversation_id
                return session
            else:
                # 工作目录变了或连接断开，关闭旧会话
                await self._close_session(user_id)

        # 创建新会话
        session = ProcessorSession(
            user_id=user_id,
            conversation_id=conversation_id,
            working_directory=working_directory,
        )

        # 创建 iFlow Client
        iflow_client = IFlowClientService(
            cwd=working_directory,
        )
        await iflow_client.connect()
        session.iflow_client = iflow_client

        # 保存会话
        self._sessions[user_id] = session
        logger.info(f"Created new IFlow session for user {user_id}, cwd={working_directory}")

        return session

    async def _close_session(self, user_id: int):
        """关闭用户会话"""
        if user_id in self._sessions:
            session = self._sessions[user_id]
            if session.iflow_client:
                try:
                    await session.iflow_client.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing IFlow client: {e}")
            del self._sessions[user_id]
            logger.debug(f"Closed IFlow session for user {user_id}")

    def get_session(self, user_id: int) -> Optional[ProcessorSession]:
        """
        获取用户会话

        Args:
            user_id: 用户 ID

        Returns:
            Optional[ProcessorSession]: 用户会话，不存在则返回 None
        """
        return self._sessions.get(user_id)

    async def close_user_session(self, user_id: int):
        """
        关闭指定用户的会话

        Args:
            user_id: 用户 ID
        """
        await self._close_session(user_id)

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

        断开信号订阅并关闭所有 iFlow 客户端连接。
        """
        self.disconnect()

        # 关闭所有用户会话
        user_ids = list(self._sessions.keys())
        for user_id in user_ids:
            await self._close_session(user_id)

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
