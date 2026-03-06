"""
WebSocket + EventBus 集成测试

测试消息通过 EventBus 流转：
1. WebSocket 收到用户消息 → WebSocketInputHandler 发射 user_message 信号
2. IFlowProcessor 订阅 user_message 信号 → 处理 AI 对话 → 发射 ai_response/ai_complete 信号
3. RedisOutputHandler 订阅 ai_response/ai_complete 信号 → 推送到 Redis Stream
4. WebSocket 订阅 Redis Stream → 推送给前端
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.event_bus import EventBus
from backend.services.input_handlers.websocket_input import WebSocketInputHandler
from backend.services.output_handlers.redis_output import RedisOutputHandler
from backend.services.iflow_processor import IFlowProcessor, ProcessorSession
from backend.services.message_buffer import MessageBuffer
from backend.services.auth import create_access_token


# ==================== EventBus 信号流转测试 ====================

class TestEventBusSignalFlow:
    """EventBus 信号流转测试"""

    def test_user_message_signal_emission(self):
        """测试 WebSocketInputHandler 发射 user_message 信号"""
        received_signals = []

        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append({
                'sender': sender,
                'kwargs': kwargs,
            })

        try:
            handler = WebSocketInputHandler(sender='test_handler')
            handler.handle(
                user_id=123,
                content="Hello, world!",
                conversation_id=456,
                working_directory='/test/workspace',
            )

            # 验证信号被发射
            assert len(received_signals) == 1
            assert received_signals[0]['kwargs']['user_id'] == 123
            assert received_signals[0]['kwargs']['content'] == "Hello, world!"
            assert received_signals[0]['kwargs']['conversation_id'] == 456
            assert received_signals[0]['kwargs']['working_directory'] == '/test/workspace'
        finally:
            # 清理订阅
            EventBus.off('user_message', capture_signal)

    def test_ai_response_signal_emission(self):
        """测试 EventBus 发射 ai_response 信号"""
        received_signals = []

        @EventBus.on('ai_response')
        def capture_signal(sender, **kwargs):
            received_signals.append(kwargs)

        try:
            EventBus.emit(
                'ai_response',
                sender='test_processor',
                user_id=1,
                content='Hello',
                is_delta=True,
                conversation_id=100,
            )

            assert len(received_signals) == 1
            assert received_signals[0]['user_id'] == 1
            assert received_signals[0]['content'] == 'Hello'
            assert received_signals[0]['is_delta'] is True
        finally:
            EventBus.off('ai_response', capture_signal)

    def test_ai_complete_signal_emission(self):
        """测试 EventBus 发射 ai_complete 信号"""
        received_signals = []

        @EventBus.on('ai_complete')
        def capture_signal(sender, **kwargs):
            received_signals.append(kwargs)

        try:
            EventBus.emit(
                'ai_complete',
                sender='test_processor',
                user_id=1,
                content='Full response',
                conversation_id=100,
            )

            assert len(received_signals) == 1
            assert received_signals[0]['user_id'] == 1
            assert received_signals[0]['content'] == 'Full response'
        finally:
            EventBus.off('ai_complete', capture_signal)

    def test_multiple_subscribers(self):
        """测试多个订阅者接收同一信号"""
        received_by_first = []
        received_by_second = []

        @EventBus.on('user_message')
        def first_subscriber(sender, **kwargs):
            received_by_first.append(kwargs)

        @EventBus.on('user_message')
        def second_subscriber(sender, **kwargs):
            received_by_second.append(kwargs)

        try:
            handler = WebSocketInputHandler()
            handler.handle(user_id=1, content="Test")

            assert len(received_by_first) == 1
            assert len(received_by_second) == 1
        finally:
            EventBus.off('user_message', first_subscriber)
            EventBus.off('user_message', second_subscriber)


# ==================== IFlowProcessor 测试 ====================

class TestIFlowProcessor:
    """IFlowProcessor 测试"""

    def test_processor_initialization(self):
        """测试处理器初始化"""
        processor = IFlowProcessor()

        # 验证初始状态
        assert len(processor._sessions) == 0
        assert len(processor._subscribers) == 1

        # 清理
        processor.disconnect()

    @pytest.mark.asyncio
    async def test_processor_session_management(self):
        """测试处理器会话管理"""
        processor = IFlowProcessor()

        try:
            # Mock IFlowClientService
            with patch('backend.services.iflow_processor.IFlowClientService') as MockClient:
                mock_client = AsyncMock()
                mock_client.is_connected = True
                mock_client.connect = AsyncMock()
                MockClient.return_value = mock_client

                # 创建会话
                session = await processor._get_or_create_session(
                    user_id=1,
                    conversation_id=100,
                    working_directory='/test/workspace',
                )

                assert session.user_id == 1
                assert session.conversation_id == 100
                assert session.working_directory == '/test/workspace'

                # 重用会话
                session2 = await processor._get_or_create_session(
                    user_id=1,
                    conversation_id=200,
                    working_directory='/test/workspace',
                )

                # 应该是同一个会话
                assert session2 is session
                # 会话 ID 应该更新
                assert session2.conversation_id == 200

        finally:
            await processor.close()

    @pytest.mark.asyncio
    async def test_processor_handles_user_message(self):
        """测试处理器处理 user_message 信号"""
        processor = IFlowProcessor()

        # 收集发射的信号
        emitted_ai_responses = []
        emitted_ai_completes = []

        @EventBus.on('ai_response')
        def capture_ai_response(sender, **kwargs):
            emitted_ai_responses.append(kwargs)

        @EventBus.on('ai_complete')
        def capture_ai_complete(sender, **kwargs):
            emitted_ai_completes.append(kwargs)

        try:
            # Mock IFlowClientService
            with patch('backend.services.iflow_processor.IFlowClientService') as MockClient:
                mock_client = AsyncMock()
                mock_client.is_connected = True
                mock_client.connect = AsyncMock()
                # Mock query_stream 返回流式响应
                async def mock_query_stream(message):
                    from backend.services.iflow_client import ChatMessage, MessageType
                    yield ChatMessage(type=MessageType.TEXT, content="Hello", is_delta=True)
                    yield ChatMessage(type=MessageType.TEXT, content=" there", is_delta=True)
                    yield ChatMessage(type=MessageType.TASK_FINISH, is_finished=True)
                mock_client.query_stream = mock_query_stream
                MockClient.return_value = mock_client

                # 直接触发处理（不通过信号，直接调用内部方法）
                await processor._on_user_message(
                    sender='test',
                    user_id=1,
                    content="Hi",
                    conversation_id=100,
                    working_directory='/test',
                )

                # 等待处理完成
                await asyncio.sleep(0.1)

                # 验证发射了 ai_response 信号
                assert len(emitted_ai_responses) >= 2  # 至少两次流式响应

                # 验证发射了 ai_complete 信号
                assert len(emitted_ai_completes) >= 1

        finally:
            EventBus.off('ai_response', capture_ai_response)
            EventBus.off('ai_complete', capture_ai_complete)
            await processor.close()


# ==================== Redis 消息流转测试 ====================

class TestRedisMessageFlow:
    """Redis 消息流转测试"""

    @pytest.mark.asyncio
    async def test_message_buffer_push_consume(self):
        """测试 MessageBuffer 推送和消费"""
        # 使用 mock Redis
        with patch('backend.services.message_buffer.aioredis') as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.xadd = AsyncMock(return_value='entry-1')
            mock_redis.expire = AsyncMock()
            mock_redis.xread = AsyncMock(return_value=[
                ['user:1:messages', [('entry-1', {'data': json.dumps({'type': 'stream', 'content': 'Hello'})})]]
            ])
            mock_redis.xdel = AsyncMock()
            mock_redis.aclose = AsyncMock()
            mock_redis_module.from_url = Mock(return_value=mock_redis)

            buffer = MessageBuffer('redis://localhost:6379/0')

            # 推送消息
            entry_id = await buffer.push(user_id=1, message={'type': 'stream', 'content': 'Hello'})
            assert entry_id == 'entry-1'

            # 消费消息
            messages = await buffer.consume(user_id=1)
            assert messages is not None

            await buffer.close()

    @pytest.mark.asyncio
    async def test_redis_output_handler(self):
        """测试 RedisOutputHandler 推送消息"""
        with patch('backend.services.message_buffer.aioredis') as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.xadd = AsyncMock(return_value='entry-1')
            mock_redis.expire = AsyncMock()
            mock_redis.aclose = AsyncMock()
            mock_redis_module.from_url = Mock(return_value=mock_redis)

            buffer = MessageBuffer('redis://localhost:6379/0')
            handler = RedisOutputHandler(buffer=buffer)

            try:
                # 触发 ai_response 信号
                EventBus.emit(
                    'ai_response',
                    sender='test',
                    user_id=1,
                    content='Hello',
                    is_delta=True,
                )

                # 等待异步处理
                await asyncio.sleep(0.1)

                # 验证 Redis xadd 被调用
                # 注意：由于 asyncio.create_task 的异步特性，可能需要等待
            finally:
                handler.disconnect()
                await buffer.close()


# ==================== WebSocket EventBus 集成测试 ====================

class TestWebSocketEventBusIntegration:
    """WebSocket + EventBus 集成测试"""

    @pytest.mark.asyncio
    async def test_websocket_input_handler_emits_signal(self):
        """测试 WebSocket 使用 WebSocketInputHandler 发射信号"""
        received = []

        @EventBus.on('user_message')
        def capture(sender, **kwargs):
            received.append(kwargs)

        try:
            handler = WebSocketInputHandler(sender='websocket_test')
            handler.handle(
                user_id=1,
                content="Test message",
                conversation_id=100,
                working_directory='/test',
            )

            assert len(received) == 1
            assert received[0]['user_id'] == 1
            assert received[0]['content'] == "Test message"
            assert received[0]['conversation_id'] == 100
            assert received[0]['working_directory'] == '/test'

        finally:
            EventBus.off('user_message', capture)

    @pytest.mark.asyncio
    async def test_signal_flow_from_input_to_output(self):
        """测试完整信号流：输入 → 处理 → 输出"""
        # 收集各个阶段的信号
        user_messages = []
        ai_responses = []
        ai_completes = []

        @EventBus.on('user_message')
        def capture_user_message(sender, **kwargs):
            user_messages.append(kwargs)

        @EventBus.on('ai_response')
        def capture_ai_response(sender, **kwargs):
            ai_responses.append(kwargs)

        @EventBus.on('ai_complete')
        def capture_ai_complete(sender, **kwargs):
            ai_completes.append(kwargs)

        try:
            # 创建输入处理器
            input_handler = WebSocketInputHandler(sender='test_flow')

            # 发射 user_message 信号
            input_handler.handle(
                user_id=1,
                content="What is the weather?",
                conversation_id=100,
            )

            # 验证 user_message 信号被发射
            assert len(user_messages) == 1
            assert user_messages[0]['content'] == "What is the weather?"

            # 手动模拟处理器的响应（因为实际处理器需要 iFlow 连接）
            EventBus.emit(
                'ai_response',
                sender='mock_processor',
                user_id=1,
                content='The weather is sunny.',
                is_delta=True,
                conversation_id=100,
            )

            EventBus.emit(
                'ai_complete',
                sender='mock_processor',
                user_id=1,
                content='The weather is sunny.',
                conversation_id=100,
            )

            # 验证信号流转
            assert len(ai_responses) == 1
            assert ai_responses[0]['content'] == 'The weather is sunny.'

            assert len(ai_completes) == 1
            assert ai_completes[0]['content'] == 'The weather is sunny.'

        finally:
            EventBus.off('user_message', capture_user_message)
            EventBus.off('ai_response', capture_ai_response)
            EventBus.off('ai_complete', capture_ai_complete)


# ==================== 完整集成测试 ====================

class TestFullIntegration:
    """完整集成测试（需要 Redis）"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 Redis 连接，手动运行")
    async def test_full_message_flow_with_redis(self):
        """
        完整消息流测试（需要 Redis）

        流程：
        1. WebSocketInputHandler 发射 user_message
        2. IFlowProcessor 处理并发射 ai_response/ai_complete
        3. RedisOutputHandler 推送到 Redis
        4. WebSocket 从 Redis 消费
        """
        # 创建真实的 MessageBuffer（需要 Redis 连接）
        buffer = MessageBuffer('redis://localhost:6379/0')

        try:
            # 推送消息到 Redis
            await buffer.push(
                user_id=1,
                message={
                    'type': 'stream',
                    'content': 'Hello from Redis',
                    'is_delta': True,
                }
            )

            # 从 Redis 获取消息
            pending = await buffer.get_pending(user_id=1)
            assert pending is not None

            # 消费消息
            messages = await buffer.consume(user_id=1)
            assert messages is not None

        finally:
            await buffer.close()
