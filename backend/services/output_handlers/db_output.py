"""
数据库输出处理器

订阅 EventBus 的 ai_complete 信号，
将完整的 AI 响应保存到数据库（ChatHistory 表）。
"""
import asyncio
import logging
from typing import Optional, Any
from datetime import datetime, timezone

from services.event_bus import EventBus

logger = logging.getLogger(__name__)


class DBOutputHandler:
    """
    数据库输出处理器

    负责订阅 AI 完成信号，将完整响应保存到数据库，
    实现输出层与数据持久化的解耦。

    使用示例：
        from sqlalchemy.ext.asyncio import AsyncSession
        from backend.database import async_session_factory

        async def create_handler():
            async with async_session_factory() as db:
                handler = DBOutputHandler(db_session=db)
                # 处理器会自动订阅信号并保存消息

        # 断开连接时
        handler.disconnect()
    """

    def __init__(self, db_session_factory=None, db_session=None):
        """
        初始化数据库输出处理器

        Args:
            db_session_factory: 异步数据库会话工厂（可选，用于创建新会话）
            db_session: 现有的数据库会话（可选，用于共享会话）
        """
        self.db_session_factory = db_session_factory
        self.db_session = db_session
        self._subscribers = []

        # 订阅信号
        self._subscribe_signals()

    def _subscribe_signals(self):
        """订阅 EventBus 信号"""
        # 订阅 ai_complete 信号
        @EventBus.on('ai_complete')
        def on_ai_complete(sender, **kwargs):
            # 创建异步任务处理
            asyncio.create_task(self._on_ai_complete(sender, **kwargs))
            return None  # 明确返回 None

        # 保存订阅者引用以便后续取消
        self._subscribers = [on_ai_complete]
        logger.debug("DBOutputHandler subscribed to ai_complete signal")

    async def _on_ai_complete(self, sender: Optional[Any], **kwargs):
        """
        处理 ai_complete 信号

        将完整响应保存到数据库。

        Args:
            sender: 信号发送者
            **kwargs: 信号参数
                - user_id (int): 用户 ID
                - content (str): 完整响应内容
                - conversation_id (int, optional): 会话 ID
                - metadata (dict, optional): 额外元数据
        """
        user_id = kwargs.get('user_id')
        content = kwargs.get('content', '')
        conversation_id = kwargs.get('conversation_id')
        metadata = kwargs.get('metadata')

        # 验证必要参数
        if user_id is None:
            logger.error("ai_complete signal missing user_id parameter")
            return

        try:
            # 保存到数据库
            await self._save_to_database(
                user_id=user_id,
                content=content,
                conversation_id=conversation_id,
                metadata=metadata
            )
            logger.debug(f"Saved ai_complete to database for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save ai_complete to database: {e}")

    async def _save_to_database(
        self,
        user_id: int,
        content: str,
        conversation_id: Optional[int] = None,
        metadata: Optional[dict] = None
    ):
        """
        将 AI 响应保存到数据库

        Args:
            user_id: 用户 ID
            content: 响应内容
            conversation_id: 会话 ID（可选）
            metadata: 额外元数据（可选，目前未使用）
        """
        # 导入模型（延迟导入避免循环依赖）
        from backend.models.user import ChatHistory

        # 确定使用的数据库会话
        db = None
        should_close = False

        try:
            if self.db_session:
                db = self.db_session
            elif self.db_session_factory:
                db = self.db_session_factory()
                should_close = True
            else:
                # 使用全局数据库工厂
                from database import async_session_factory
                db = async_session_factory()
                should_close = True

            # 创建聊天历史记录
            chat_message = ChatHistory(
                user_id=user_id,
                role="assistant",
                content=content,
                conversation_id=conversation_id,
                created_at=datetime.now(timezone.utc)
            )

            db.add(chat_message)
            await db.commit()
            await db.refresh(chat_message)

            logger.info(
                f"Saved assistant message: user_id={user_id}, "
                f"message_id={chat_message.id}, "
                f"conversation_id={conversation_id}"
            )

        finally:
            # 只关闭自己创建的会话
            if should_close and db:
                await db.close()

    def disconnect(self):
        """
        断开信号订阅

        在不再需要接收消息时调用，取消所有信号订阅。
        """
        for subscriber in self._subscribers:
            try:
                EventBus.ai_complete.disconnect(subscriber)
            except Exception:
                pass

        self._subscribers.clear()
        logger.debug("DBOutputHandler disconnected from signals")

    async def close(self):
        """
        关闭处理器（断开订阅并清理资源）

        这是 disconnect 的异步版本，提供一致的 API。
        """
        self.disconnect()
