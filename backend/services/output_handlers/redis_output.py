"""
Redis 输出处理器

订阅 EventBus 的 ai_response 和 ai_complete 信号，
将消息推送到 Redis Stream，用于 WebSocket 断线重连后恢复消息。

使用队列 + 单消费者模式保证消息顺序：
- 所有信号处理函数只负责将消息放入队列
- 单独的消费者协程按顺序处理队列中的消息
- 避免多个 asyncio.create_task 导致的执行顺序问题
"""
import asyncio
import logging
from typing import Optional, Any
from dataclasses import dataclass

from backend.services.event_bus import EventBus
from backend.services.message_buffer import MessageBuffer

logger = logging.getLogger(__name__)


@dataclass
class QueuedMessage:
    """队列中的消息项"""
    signal_type: str  # 'ai_response', 'ai_complete', 'tool_call'
    kwargs: dict      # 信号参数


class RedisOutputHandler:
    """
    Redis 输出处理器

    负责订阅 AI 响应信号，将消息推送到 Redis Stream，
    实现输出层与 WebSocket 的解耦。

    使用队列 + 单消费者模式保证消息顺序，避免并发写入导致乱序。

    使用示例：
        buffer = MessageBuffer("redis://localhost:6379/0")
        handler = RedisOutputHandler(buffer=buffer)

        # 启动消费者协程
        await handler.start()

        # 断开连接时
        await handler.stop()
    """

    def __init__(self, buffer: MessageBuffer):
        """
        初始化 Redis 输出处理器

        Args:
            buffer: MessageBuffer 实例，用于推送消息到 Redis
        """
        self.buffer = buffer
        self._subscribers = []
        
        # 消息队列：保证顺序处理
        self._queue: asyncio.Queue[QueuedMessage] = asyncio.Queue()
        # 消费者任务
        self._consumer_task: Optional[asyncio.Task] = None
        # 停止标志
        self._stop_event = asyncio.Event()

        # 订阅信号
        self._subscribe_signals()

    async def start(self):
        """启动消费者协程"""
        if self._consumer_task is None:
            self._stop_event.clear()
            self._consumer_task = asyncio.create_task(self._consumer_loop())
            logger.debug("RedisOutputHandler consumer started")

    async def stop(self):
        """停止消费者协程"""
        if self._consumer_task:
            self._stop_event.set()
            # 放入一个空消息来唤醒消费者
            await self._queue.put(QueuedMessage(signal_type='', kwargs={}))
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
            logger.debug("RedisOutputHandler consumer stopped")

    async def _consumer_loop(self):
        """
        消费者协程：按顺序处理队列中的消息

        这是保证消息顺序的关键：
        - 所有消息按放入队列的顺序处理
        - 每条消息处理完成后才处理下一条
        - 避免 asyncio.create_task 导致的乱序
        """
        while not self._stop_event.is_set():
            try:
                # 等待消息
                msg = await self._queue.get()
                
                if self._stop_event.is_set() or not msg.signal_type:
                    break
                
                # 根据信号类型处理
                if msg.signal_type == 'ai_response':
                    await self._handle_ai_response(**msg.kwargs)
                elif msg.signal_type == 'ai_complete':
                    await self._handle_ai_complete(**msg.kwargs)
                elif msg.signal_type == 'tool_call':
                    await self._handle_tool_call(**msg.kwargs)
                
                self._queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}")

    def _subscribe_signals(self):
        """订阅 EventBus 信号"""
        # 订阅 ai_response 信号
        @EventBus.on('ai_response')
        def on_ai_response(sender, **kwargs):
            # 放入队列，由消费者按顺序处理
            self._queue.put_nowait(QueuedMessage(signal_type='ai_response', kwargs=kwargs))
            return None

        # 订阅 ai_complete 信号
        @EventBus.on('ai_complete')
        def on_ai_complete(sender, **kwargs):
            # 放入队列，由消费者按顺序处理
            self._queue.put_nowait(QueuedMessage(signal_type='ai_complete', kwargs=kwargs))
            return None

        # 订阅 tool_call 信号
        @EventBus.on('tool_call')
        def on_tool_call(sender, **kwargs):
            # 放入队列，由消费者按顺序处理
            self._queue.put_nowait(QueuedMessage(signal_type='tool_call', kwargs=kwargs))
            return None

        # 保存订阅者引用以便后续取消
        self._subscribers = [on_ai_response, on_ai_complete, on_tool_call]
        logger.debug("RedisOutputHandler subscribed to ai_response, ai_complete, and tool_call signals")

    async def _handle_ai_response(self, **kwargs):
        """
        处理 ai_response 信号

        将流式响应推送到 Redis Stream。
        """
        user_id = kwargs.get('user_id')
        content = kwargs.get('content', '')
        is_delta = kwargs.get('is_delta', True)
        conversation_id = kwargs.get('conversation_id')
        request_id = kwargs.get('request_id')
        metadata = kwargs.get('metadata')

        # 构建消息
        message = {
            'type': 'stream',
            'content': content,
            'is_delta': is_delta,
        }

        if conversation_id is not None:
            message['conversation_id'] = conversation_id
        if request_id is not None:
            message['request_id'] = request_id
        if metadata:
            message['metadata'] = metadata

        try:
            await self.buffer.push(user_id=user_id, message=message)
            logger.debug(f"Pushed ai_response to Redis for user {user_id}, request_id={request_id}")
        except Exception as e:
            logger.error(f"Failed to push ai_response to Redis: {e}")

    async def _handle_ai_complete(self, **kwargs):
        """
        处理 ai_complete 信号

        将完整响应推送到 Redis Stream。
        """
        user_id = kwargs.get('user_id')
        content = kwargs.get('content', '')
        conversation_id = kwargs.get('conversation_id')
        request_id = kwargs.get('request_id')
        metadata = kwargs.get('metadata')

        # 构建消息
        message = {
            'type': 'complete',
            'content': content,
        }

        if conversation_id is not None:
            message['conversation_id'] = conversation_id
        if request_id is not None:
            message['request_id'] = request_id
        if metadata:
            message['metadata'] = metadata

        try:
            await self.buffer.push(user_id=user_id, message=message)
            logger.debug(f"Pushed ai_complete to Redis for user {user_id}, request_id={request_id}")
        except Exception as e:
            logger.error(f"Failed to push ai_complete to Redis: {e}")

    async def _handle_tool_call(self, **kwargs):
        """
        处理 tool_call 信号

        将工具调用推送到 Redis Stream。
        """
        user_id = kwargs.get('user_id')
        tool_id = kwargs.get('tool_id')
        tool_name = kwargs.get('tool_name', 'unknown')
        arguments = kwargs.get('arguments', {})
        status = kwargs.get('status', 'in_progress')
        result = kwargs.get('result')
        error = kwargs.get('error')
        conversation_id = kwargs.get('conversation_id')
        request_id = kwargs.get('request_id')

        # 构建消息
        message = {
            'type': 'tool_call',
            'tool_id': tool_id,
            'tool_name': tool_name,
            'arguments': arguments,
            'status': status,
        }

        if result is not None:
            message['result'] = result
        if error:
            message['error'] = error
        if conversation_id is not None:
            message['conversation_id'] = conversation_id
        if request_id is not None:
            message['request_id'] = request_id

        try:
            await self.buffer.push(user_id=user_id, message=message)
            logger.debug(f"Pushed tool_call to Redis for user {user_id}, tool={tool_name}, status={status}")
        except Exception as e:
            logger.error(f"Failed to push tool_call to Redis: {e}")

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
            try:
                EventBus.tool_call.disconnect(subscriber)
            except Exception:
                pass

        self._subscribers.clear()
        logger.debug("RedisOutputHandler disconnected from signals")