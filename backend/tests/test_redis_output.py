"""
RedisOutputHandler 单元测试

测试 Redis 输出处理器正确订阅 ai_response 和 ai_complete 信号并推送消息。
"""
import sys
import os

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.event_bus import EventBus


class TestRedisOutputHandler:
    """RedisOutputHandler 测试类"""

    def setup_method(self):
        """每个测试方法前清理信号订阅"""
        EventBus.ai_response.receivers.clear()
        EventBus.ai_complete.receivers.clear()

    @pytest.mark.asyncio
    async def test_handler_initialization(self):
        """测试处理器初始化"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        assert handler is not None
        assert handler.buffer == mock_buffer

    @pytest.mark.asyncio
    async def test_ai_response_signal_pushes_message(self):
        """测试 ai_response 信号触发消息推送"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        mock_buffer.push.return_value = "entry_123"
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        # 发射 ai_response 信号
        EventBus.emit(
            'ai_response',
            sender='iflow_client',
            user_id=123,
            content="Hello",
            is_delta=True
        )
        
        # 给异步处理器一些时间执行
        await asyncio.sleep(0.1)
        
        # 验证 push 被调用
        mock_buffer.push.assert_called_once()
        call_args = mock_buffer.push.call_args
        assert call_args.kwargs['user_id'] == 123
        message = call_args.kwargs['message']
        assert message['type'] == 'stream'
        assert message['content'] == "Hello"
        assert message['is_delta'] is True

    @pytest.mark.asyncio
    async def test_ai_complete_signal_pushes_message(self):
        """测试 ai_complete 信号触发消息推送"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        mock_buffer.push.return_value = "entry_456"
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        # 发射 ai_complete 信号
        EventBus.emit(
            'ai_complete',
            sender='iflow_client',
            user_id=123,
            content="Complete response",
            conversation_id=456
        )
        
        # 给异步处理器一些时间执行
        await asyncio.sleep(0.1)
        
        # 验证 push 被调用
        mock_buffer.push.assert_called_once()
        call_args = mock_buffer.push.call_args
        assert call_args.kwargs['user_id'] == 123
        message = call_args.kwargs['message']
        assert message['type'] == 'complete'
        assert message['content'] == "Complete response"
        assert message['conversation_id'] == 456

    @pytest.mark.asyncio
    async def test_ai_response_with_metadata(self):
        """测试 ai_response 信号支持 metadata"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        # 发射带 metadata 的 ai_response 信号
        EventBus.emit(
            'ai_response',
            sender='iflow_client',
            user_id=1,
            content="test",
            is_delta=True,
            metadata={'model': 'gpt-4', 'tokens': 100}
        )
        
        await asyncio.sleep(0.1)
        
        call_args = mock_buffer.push.call_args
        message = call_args.kwargs['message']
        assert message['metadata'] == {'model': 'gpt-4', 'tokens': 100}

    @pytest.mark.asyncio
    async def test_ai_complete_without_conversation_id(self):
        """测试 ai_complete 信号支持无 conversation_id"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        # 发射不带 conversation_id 的 ai_complete 信号
        EventBus.emit(
            'ai_complete',
            sender='iflow_client',
            user_id=1,
            content="test"
        )
        
        await asyncio.sleep(0.1)
        
        call_args = mock_buffer.push.call_args
        message = call_args.kwargs['message']
        assert 'conversation_id' not in message

    @pytest.mark.asyncio
    async def test_multiple_signals(self):
        """测试多个信号触发多次推送"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        # 连续发射多个信号
        EventBus.emit('ai_response', user_id=1, content="chunk1", is_delta=True)
        EventBus.emit('ai_response', user_id=1, content="chunk2", is_delta=True)
        EventBus.emit('ai_complete', user_id=1, content="full response")
        
        await asyncio.sleep(0.1)
        
        # 验证 push 被调用 3 次
        assert mock_buffer.push.call_count == 3

    @pytest.mark.asyncio
    async def test_disconnect_removes_subscriptions(self):
        """测试断开连接后取消订阅"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        # 断开连接
        handler.disconnect()
        
        # 发射信号
        EventBus.emit('ai_response', user_id=1, content="test", is_delta=True)
        
        await asyncio.sleep(0.1)
        
        # push 不应该被调用
        mock_buffer.push.assert_not_called()


class TestRedisOutputHandlerEdgeCases:
    """边界场景测试"""

    def setup_method(self):
        """每个测试方法前清理信号订阅"""
        EventBus.ai_response.receivers.clear()
        EventBus.ai_complete.receivers.clear()

    @pytest.mark.asyncio
    async def test_unicode_content(self):
        """测试处理 Unicode 内容"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        unicode_content = "你好世界 🌍 مرحبا"
        EventBus.emit('ai_response', user_id=1, content=unicode_content, is_delta=True)
        
        await asyncio.sleep(0.1)
        
        call_args = mock_buffer.push.call_args
        message = call_args.kwargs['message']
        assert message['content'] == unicode_content

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """测试处理空内容"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        EventBus.emit('ai_response', user_id=1, content="", is_delta=True)
        
        await asyncio.sleep(0.1)
        
        call_args = mock_buffer.push.call_args
        message = call_args.kwargs['message']
        assert message['content'] == ""

    @pytest.mark.asyncio
    async def test_long_content(self):
        """测试处理长内容"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        long_content = "a" * 10000
        EventBus.emit('ai_complete', user_id=1, content=long_content)
        
        await asyncio.sleep(0.1)
        
        call_args = mock_buffer.push.call_args
        message = call_args.kwargs['message']
        assert message['content'] == long_content

    @pytest.mark.asyncio
    async def test_special_characters(self):
        """测试处理特殊字符"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        special_content = '<script>alert("xss")</script>\n\t\r```code```'
        EventBus.emit('ai_response', user_id=1, content=special_content, is_delta=True)
        
        await asyncio.sleep(0.1)
        
        call_args = mock_buffer.push.call_args
        message = call_args.kwargs['message']
        assert message['content'] == special_content

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        """测试多个处理器实例"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer_1 = AsyncMock()
        mock_buffer_2 = AsyncMock()
        
        handler_1 = RedisOutputHandler(buffer=mock_buffer_1)
        handler_2 = RedisOutputHandler(buffer=mock_buffer_2)
        
        EventBus.emit('ai_response', user_id=1, content="test", is_delta=True)
        
        await asyncio.sleep(0.1)
        
        # 两个处理器都应该收到信号
        mock_buffer_1.push.assert_called_once()
        mock_buffer_2.push.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_delta_false(self):
        """测试 is_delta=False 的情况"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        EventBus.emit('ai_response', user_id=1, content="full chunk", is_delta=False)
        
        await asyncio.sleep(0.1)
        
        call_args = mock_buffer.push.call_args
        message = call_args.kwargs['message']
        assert message['is_delta'] is False

    @pytest.mark.asyncio
    async def test_complex_metadata(self):
        """测试复杂 metadata 结构"""
        from services.output_handlers.redis_output import RedisOutputHandler
        
        mock_buffer = AsyncMock()
        
        handler = RedisOutputHandler(buffer=mock_buffer)
        
        complex_metadata = {
            'model': 'gpt-4',
            'tokens': {'input': 100, 'output': 200},
            'timing': {'first_token': 0.5, 'total': 2.3},
            'flags': ['streaming', 'cached']
        }
        
        EventBus.emit(
            'ai_complete',
            user_id=1,
            content="test",
            metadata=complex_metadata
        )
        
        await asyncio.sleep(0.1)
        
        call_args = mock_buffer.push.call_args
        message = call_args.kwargs['message']
        assert message['metadata'] == complex_metadata
