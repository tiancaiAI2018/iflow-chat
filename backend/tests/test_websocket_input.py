"""
WebSocketInputHandler 单元测试

测试 WebSocket 输入处理器正确发射 user_message 信号。
"""
import sys
import os

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.services.input_handlers.websocket_input import WebSocketInputHandler
from backend.services.event_bus import EventBus


class TestWebSocketInputHandler:
    """WebSocketInputHandler 测试类"""

    def setup_method(self):
        """每个测试方法前清理信号订阅"""
        # 断开所有 user_message 信号的订阅
        EventBus.user_message.receivers.clear()

    def test_handler_initialization(self):
        """测试处理器初始化"""
        handler = WebSocketInputHandler()
        assert handler is not None

    def test_handle_emits_user_message_signal(self):
        """测试 handle 方法发射 user_message 信号"""
        handler = WebSocketInputHandler()
        
        # 记录信号接收
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append({
                'sender': sender,
                'kwargs': kwargs
            })
        
        # 调用 handle
        handler.handle(
            user_id=123,
            content="Hello, world!",
            conversation_id=456
        )
        
        # 验证信号被发射
        assert len(received_signals) == 1
        assert received_signals[0]['kwargs']['user_id'] == 123
        assert received_signals[0]['kwargs']['content'] == "Hello, world!"
        assert received_signals[0]['kwargs']['conversation_id'] == 456

    def test_handle_with_sender(self):
        """测试 handle 方法支持 sender 参数"""
        handler = WebSocketInputHandler(sender='websocket_client')
        
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append({
                'sender': sender,
                'kwargs': kwargs
            })
        
        handler.handle(user_id=1, content="test")
        
        assert len(received_signals) == 1
        assert received_signals[0]['sender'] == 'websocket_client'

    def test_handle_without_conversation_id(self):
        """测试 handle 方法支持无 conversation_id"""
        handler = WebSocketInputHandler()
        
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append(kwargs)
        
        handler.handle(user_id=1, content="test")
        
        assert len(received_signals) == 1
        assert received_signals[0]['user_id'] == 1
        assert received_signals[0]['content'] == "test"
        assert 'conversation_id' not in received_signals[0]

    def test_handle_with_metadata(self):
        """测试 handle 方法支持额外元数据"""
        handler = WebSocketInputHandler()
        
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append(kwargs)
        
        handler.handle(
            user_id=1,
            content="test",
            metadata={'source': 'mobile', 'version': '1.0'}
        )
        
        assert len(received_signals) == 1
        assert received_signals[0]['metadata'] == {'source': 'mobile', 'version': '1.0'}

    def test_multiple_subscribers_receive_signal(self):
        """测试多个订阅者都能接收到信号"""
        handler = WebSocketInputHandler()
        
        received_1 = []
        received_2 = []
        
        @EventBus.on('user_message')
        def subscriber1(sender, **kwargs):
            received_1.append(kwargs)
        
        @EventBus.on('user_message')
        def subscriber2(sender, **kwargs):
            received_2.append(kwargs)
        
        handler.handle(user_id=1, content="broadcast")
        
        assert len(received_1) == 1
        assert len(received_2) == 1
        assert received_1[0]['content'] == "broadcast"
        assert received_2[0]['content'] == "broadcast"

    def test_handle_with_unicode_content(self):
        """测试处理 Unicode 内容"""
        handler = WebSocketInputHandler()
        
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append(kwargs)
        
        unicode_content = "你好世界 🌍 مرحبا"
        handler.handle(user_id=1, content=unicode_content)
        
        assert len(received_signals) == 1
        assert received_signals[0]['content'] == unicode_content

    def test_handle_with_empty_content(self):
        """测试处理空内容"""
        handler = WebSocketInputHandler()
        
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append(kwargs)
        
        handler.handle(user_id=1, content="")
        
        assert len(received_signals) == 1
        assert received_signals[0]['content'] == ""

    def test_handle_with_long_content(self):
        """测试处理长内容"""
        handler = WebSocketInputHandler()
        
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append(kwargs)
        
        long_content = "a" * 10000
        handler.handle(user_id=1, content=long_content)
        
        assert len(received_signals) == 1
        assert received_signals[0]['content'] == long_content

    def test_handle_multiple_calls(self):
        """测试多次调用 handle 方法"""
        handler = WebSocketInputHandler()
        
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append(kwargs)
        
        for i in range(5):
            handler.handle(user_id=i, content=f"message_{i}")
        
        assert len(received_signals) == 5
        for i, signal in enumerate(received_signals):
            assert signal['user_id'] == i
            assert signal['content'] == f"message_{i}"


class TestWebSocketInputHandlerEdgeCases:
    """边界场景测试"""

    def setup_method(self):
        """每个测试方法前清理信号订阅"""
        EventBus.user_message.receivers.clear()

    def test_handle_with_special_characters(self):
        """测试处理特殊字符"""
        handler = WebSocketInputHandler()
        
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append(kwargs)
        
        special_content = '<script>alert("xss")</script>\n\t\r'
        handler.handle(user_id=1, content=special_content)
        
        assert len(received_signals) == 1
        assert received_signals[0]['content'] == special_content

    def test_handle_with_none_sender(self):
        """测试 sender 为 None"""
        handler = WebSocketInputHandler(sender=None)
        
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append({
                'sender': sender,
                'kwargs': kwargs
            })
        
        handler.handle(user_id=1, content="test")
        
        assert len(received_signals) == 1
        assert received_signals[0]['sender'] is None

    def test_handle_preserves_original_kwargs(self):
        """测试 handle 方法保留原始参数"""
        handler = WebSocketInputHandler()
        
        received_signals = []
        
        @EventBus.on('user_message')
        def capture_signal(sender, **kwargs):
            received_signals.append(kwargs)
        
        extra_data = {'key1': 'value1', 'key2': {'nested': True}}
        handler.handle(
            user_id=1,
            content="test",
            extra=extra_data
        )
        
        assert len(received_signals) == 1
        assert received_signals[0]['extra'] == extra_data
