"""
Redis 输出处理器

订阅 EventBus 的 ai_response 和 ai_complete 信号，
将消息推送到 Redis Stream，用于 WebSocket 断线重连后恢复消息。
"""
import asyncio
import logging
from typing import Optional, Any

from services.event_bus import EventBus
from services.message_buffer import MessageBuffer

logger = logging.getLogger(__name__)


class RedisOutputHandler:
    """
    Redis 输出处理器

    负责订阅 AI 响应信号，将消息推送到 Redis Stream，
    实现输出层与 WebSocket 的解耦。

    使用示例：
        buffer = MessageBuffer("redis://localhost:6379/0")
        handler = RedisOutputHandler(buffer=buffer)

        # 处理器会自动订阅信号并推送消息

        # 断开连接时
        handler.disconnect()
    """

    def __init__(self, buffer: MessageBuffer):
        """
        初始化 Redis 输出处理器

        Args:
            buffer: MessageBuffer 实例，用于推送消息到 Redis
        """
        self.buffer = buffer
        self._subscribers = []

        # 订阅信号
        self._subscribe_signals()

    def _subscribe_signals(self):
        """订阅 EventBus 信号"""
        # 订阅 ai_response 信号
        @EventBus.on('ai_response')
        def on_ai_response(sender, **kwargs):
            # 创建异步任务处理
            asyncio.create_task(self._on_ai_response(sender, **kwargs))
            return None  # 明确返回 None

        # 订阅 ai_complete 信号
        @EventBus.on('ai_complete')
        def on_ai_complete(sender, **kwargs):
            # 创建异步任务处理
            asyncio.create_task(self._on_ai_complete(sender, **kwargs))
            return None  # 明确返回 None

        # 保存订阅者引用以便后续取消
        self._subscribers = [on_ai_response, on_ai_complete]
        logger.debug("RedisOutputHandler subscribed to ai_response and ai_complete signals")

    async def _on_ai_response(self, sender: Optional[Any], **kwargs):
        """
        处理 ai_response 信号

        将流式响应推送到 Redis Stream。

        Args:
            sender: 信号发送者
            **kwargs: 信号参数
                - user_id (int): 用户 ID
                - content (str): 响应内容
                - is_delta (bool): 是否增量内容
                - metadata (dict, optional): 额外元数据
        """
        user_id = kwargs.get('user_id')
        content = kwargs.get('content', '')
        is_delta = kwargs.get('is_delta', True)
        metadata = kwargs.get('metadata')

        # 构建消息
        message = {
            'type': 'stream',
            'content': content,
            'is_delta': is_delta,
        }

        # 添加可选的 metadata
        if metadata:
            message['metadata'] = metadata

        try:
            await self.buffer.push(user_id=user_id, message=message)
            logger.debug(f"Pushed ai_response to Redis for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to push ai_response to Redis: {e}")

    async def _on_ai_complete(self, sender: Optional[Any], **kwargs):
        """
        处理 ai_complete 信号

        将完整响应推送到 Redis Stream。

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

        # 构建消息
        message = {
            'type': 'complete',
            'content': content,
        }

        # 添加可选的 conversation_id
        if conversation_id is not None:
            message['conversation_id'] = conversation_id

        # 添加可选的 metadata
        if metadata:
            message['metadata'] = metadata

        try:
            await self.buffer.push(user_id=user_id, message=message)
            logger.debug(f"Pushed ai_complete to Redis for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to push ai_complete to Redis: {e}")

    def disconnect(self):
        """
        断开信号订阅

        在不再需要接收消息时调用，取消所有信号订阅。
        """
        for subscriber in self._subscribers:
            try:
                EventBus.ai_response.disconnect(subscriber)
            except Exception:
                pass
            try:
                EventBus.ai_complete.disconnect(subscriber)
            except Exception:
                pass

        self._subscribers.clear()
        logger.debug("RedisOutputHandler disconnected from signals")
