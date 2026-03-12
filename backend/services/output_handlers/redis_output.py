"""
Redis 输出处理器

订阅 EventBus 的 ai_response 和 ai_complete 信号，
将消息推送到 Redis Stream，用于 WebSocket 断线重连后恢复消息。

使用队列 + 单消费者模式保证消息顺序：
- 所有信号处理函数只负责将消息放入队列
- 单独的消费者协程按顺序处理队列中的消息
- 避免多个 asyncio.create_task 导致的执行顺序问题

优化：对普通文本消息进行批量累积发送，减少 Redis 网络 IO：
- tool_call 和 complete 消息立即发送（保证用户体验）
- 普通文本消息累积到一定数量或超时后批量发送
"""
import asyncio
import logging
import time
from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field

from backend.services.event_bus import EventBus
from backend.services.message_buffer import MessageBuffer

logger = logging.getLogger(__name__)


# 批量发送配置
BATCH_SIZE_THRESHOLD = 500  # 累积字符数阈值
BATCH_TIME_THRESHOLD = 0.1  # 累积时间阈值（秒）


@dataclass
class QueuedMessage:
    """队列中的消息项"""
    signal_type: str  # 'ai_response', 'ai_complete', 'tool_call', 'plan'
    kwargs: dict      # 信号参数


@dataclass
class BatchBuffer:
    """批量消息缓冲区"""
    user_id: int
    conversation_id: Optional[int] = None
    request_id: Optional[str] = None
    content_parts: List[str] = field(default_factory=list)
    total_chars: int = 0
    first_message_time: float = field(default_factory=time.time)


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
        
        # 批量发送缓冲区：key = (user_id, conversation_id, request_id)
        self._batch_buffers: Dict[tuple, BatchBuffer] = {}
        # 批量刷新任务
        self._flush_task: Optional[asyncio.Task] = None

        # 订阅信号
        self._subscribe_signals()

    async def start(self):
        """启动消费者协程和批量刷新任务"""
        if self._consumer_task is None:
            self._stop_event.clear()
            self._consumer_task = asyncio.create_task(self._consumer_loop())
            self._flush_task = asyncio.create_task(self._batch_flush_loop())
            logger.debug("RedisOutputHandler consumer and flush task started")

    async def stop(self):
        """停止消费者协程和批量刷新任务"""
        # 先刷新所有剩余的批量消息
        await self._flush_all_batches()
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        
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
                elif msg.signal_type == 'plan':
                    await self._handle_plan(**msg.kwargs)
                
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

        # 订阅 plan 信号
        @EventBus.on('plan')
        def on_plan(sender, **kwargs):
            # 放入队列，由消费者按顺序处理
            self._queue.put_nowait(QueuedMessage(signal_type='plan', kwargs=kwargs))
            return None

        # 保存订阅者引用以便后续取消
        self._subscribers = [on_ai_response, on_ai_complete, on_tool_call, on_plan]
        logger.debug("RedisOutputHandler subscribed to ai_response, ai_complete, tool_call, and plan signals")

    async def _handle_ai_response(self, **kwargs):
        """
        处理 ai_response 信号

        对普通文本消息进行批量累积发送，减少 Redis 网络 IO。
        如果消息包含 metadata.error 标记，则立即发送。
        """
        user_id = kwargs.get('user_id')
        content = kwargs.get('content', '')
        is_delta = kwargs.get('is_delta', True)
        conversation_id = kwargs.get('conversation_id')
        request_id = kwargs.get('request_id')
        metadata = kwargs.get('metadata')

        # 错误消息立即发送
        if metadata and metadata.get('error'):
            message = {
                'type': 'stream',
                'content': content,
                'is_delta': False,
            }
            if conversation_id is not None:
                message['conversation_id'] = conversation_id
            if request_id is not None:
                message['request_id'] = request_id
            message['metadata'] = metadata
            
            try:
                await self.buffer.push(user_id=user_id, message=message)
                logger.debug(f"Pushed error ai_response to Redis for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to push ai_response to Redis: {e}")
            return

        # 普通文本消息：累积到批量缓冲区
        if not content:
            return

        buffer_key = (user_id, conversation_id, request_id)
        
        if buffer_key not in self._batch_buffers:
            self._batch_buffers[buffer_key] = BatchBuffer(
                user_id=user_id,
                conversation_id=conversation_id,
                request_id=request_id,
            )
        
        batch = self._batch_buffers[buffer_key]
        batch.content_parts.append(content)
        batch.total_chars += len(content)
        
        # 如果累积字符数超过阈值，立即刷新
        if batch.total_chars >= BATCH_SIZE_THRESHOLD:
            await self._flush_batch(buffer_key)

    async def _flush_batch(self, buffer_key: tuple):
        """刷新单个批量缓冲区"""
        batch = self._batch_buffers.pop(buffer_key, None)
        if not batch or not batch.content_parts:
            return
        
        # 合并所有内容
        combined_content = ''.join(batch.content_parts)
        
        message = {
            'type': 'stream',
            'content': combined_content,
            'is_delta': True,
        }
        
        if batch.conversation_id is not None:
            message['conversation_id'] = batch.conversation_id
        if batch.request_id is not None:
            message['request_id'] = batch.request_id
        
        try:
            await self.buffer.push(user_id=batch.user_id, message=message)
            logger.debug(f"Flushed batch to Redis: user={batch.user_id}, chars={batch.total_chars}")
        except Exception as e:
            logger.error(f"Failed to flush batch to Redis: {e}")

    async def _flush_all_batches(self):
        """刷新所有批量缓冲区"""
        for buffer_key in list(self._batch_buffers.keys()):
            await self._flush_batch(buffer_key)

    async def _batch_flush_loop(self):
        """定时刷新批量缓冲区"""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(BATCH_TIME_THRESHOLD)
                
                # 检查所有缓冲区，刷新超时的
                current_time = time.time()
                keys_to_flush = []
                
                for buffer_key, batch in list(self._batch_buffers.items()):
                    if current_time - batch.first_message_time >= BATCH_TIME_THRESHOLD:
                        keys_to_flush.append(buffer_key)
                
                for key in keys_to_flush:
                    await self._flush_batch(key)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch flush loop: {e}")

    async def _handle_ai_complete(self, **kwargs):
        """
        处理 ai_complete 信号

        先刷新该请求的批量缓冲区，然后将完整响应推送到 Redis Stream。
        """
        user_id = kwargs.get('user_id')
        content = kwargs.get('content', '')
        conversation_id = kwargs.get('conversation_id')
        request_id = kwargs.get('request_id')
        metadata = kwargs.get('metadata')

        # 先刷新该请求的批量缓冲区
        buffer_key = (user_id, conversation_id, request_id)
        await self._flush_batch(buffer_key)

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

        先刷新该请求的批量缓冲区，然后将工具调用推送到 Redis Stream。
        这样可以确保工具调用消息的顺序正确。
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

        # 先刷新该请求的批量缓冲区，确保工具调用前所有文本已发送
        buffer_key = (user_id, conversation_id, request_id)
        await self._flush_batch(buffer_key)

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

    async def _handle_plan(self, **kwargs):
        """
        处理 plan 信号

        先刷新该请求的批量缓冲区，然后将任务计划推送到 Redis Stream。
        """
        user_id = kwargs.get('user_id')
        entries = kwargs.get('entries', [])
        conversation_id = kwargs.get('conversation_id')
        request_id = kwargs.get('request_id')

        # 先刷新该请求的批量缓冲区
        buffer_key = (user_id, conversation_id, request_id)
        await self._flush_batch(buffer_key)

        # 构建消息
        message = {
            'type': 'plan',
            'entries': entries,
        }

        if conversation_id is not None:
            message['conversation_id'] = conversation_id
        if request_id is not None:
            message['request_id'] = request_id

        try:
            await self.buffer.push(user_id=user_id, message=message)
            logger.debug(f"Pushed plan to Redis for user {user_id}, entries={len(entries)}")
        except Exception as e:
            logger.error(f"Failed to push plan to Redis: {e}")


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
            try:
                EventBus.plan.disconnect(subscriber)
            except Exception:
                pass

        self._subscribers.clear()
        logger.debug("RedisOutputHandler disconnected from signals")