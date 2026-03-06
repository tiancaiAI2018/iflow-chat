"""
EventBus 信号系统单元测试

测试目标：
- 信号定义正确（user_message, ai_response, ai_complete）
- emit 方法正确发射信号
- on 装饰器正确订阅信号
- 信号参数正确传递
"""
import sys
import os

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from blinker import Signal
from unittest.mock import AsyncMock, MagicMock
import asyncio


class TestEventBusSignals:
    """测试 EventBus 信号定义"""

    def test_event_bus_has_user_message_signal(self):
        """测试 EventBus 包含 user_message 信号"""
        from services.event_bus import EventBus

        assert hasattr(EventBus, 'user_message'), "EventBus 应该有 user_message 信号"
        assert isinstance(EventBus.user_message, Signal), "user_message 应该是 Signal 类型"

    def test_event_bus_has_ai_response_signal(self):
        """测试 EventBus 包含 ai_response 信号"""
        from services.event_bus import EventBus

        assert hasattr(EventBus, 'ai_response'), "EventBus 应该有 ai_response 信号"
        assert isinstance(EventBus.ai_response, Signal), "ai_response 应该是 Signal 类型"

    def test_event_bus_has_ai_complete_signal(self):
        """测试 EventBus 包含 ai_complete 信号"""
        from services.event_bus import EventBus

        assert hasattr(EventBus, 'ai_complete'), "EventBus 应该有 ai_complete 信号"
        assert isinstance(EventBus.ai_complete, Signal), "ai_complete 应该是 Signal 类型"


class TestEventBusEmit:
    """测试 EventBus emit 方法"""

    def test_emit_user_message_signal(self):
        """测试发射 user_message 信号"""
        from services.event_bus import EventBus

        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        # 连接处理器
        EventBus.user_message.connect(handler)

        EventBus.emit('user_message', user_id=1, content="hello", conversation_id=100)

        assert len(received) == 1
        assert received[0]['user_id'] == 1
        assert received[0]['content'] == "hello"
        assert received[0]['conversation_id'] == 100

        # 清理连接
        EventBus.user_message.disconnect(handler)

    def test_emit_ai_response_signal(self):
        """测试发射 ai_response 信号"""
        from services.event_bus import EventBus

        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        EventBus.ai_response.connect(handler)

        EventBus.emit('ai_response', user_id=2, content="AI response chunk", is_delta=True)

        assert len(received) == 1
        assert received[0]['user_id'] == 2
        assert received[0]['content'] == "AI response chunk"
        assert received[0]['is_delta'] is True

        # 清理连接
        EventBus.ai_response.disconnect(handler)

    def test_emit_ai_complete_signal(self):
        """测试发射 ai_complete 信号"""
        from services.event_bus import EventBus

        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        EventBus.ai_complete.connect(handler)

        EventBus.emit('ai_complete', user_id=3, content="Full AI response", conversation_id=200)

        assert len(received) == 1
        assert received[0]['user_id'] == 3
        assert received[0]['content'] == "Full AI response"
        assert received[0]['conversation_id'] == 200

        # 清理连接
        EventBus.ai_complete.disconnect(handler)

    def test_emit_with_sender(self):
        """测试带 sender 的信号发射"""
        from services.event_bus import EventBus

        received_sender = []

        def handler(sender, **kwargs):
            received_sender.append(sender)

        EventBus.user_message.connect(handler)

        EventBus.emit('user_message', sender="websocket_handler", user_id=1, content="test")

        assert received_sender[0] == "websocket_handler"

        # 清理连接
        EventBus.user_message.disconnect(handler)


class TestEventBusOnDecorator:
    """测试 EventBus on 装饰器"""

    def test_on_decorator_returns_function(self):
        """测试 on 装饰器返回可调用函数"""
        from services.event_bus import EventBus

        decorator = EventBus.on('user_message')
        assert callable(decorator)

        # 测试装饰函数
        @decorator
        def my_handler(sender, **kwargs):
            pass

        assert callable(my_handler)

        # 清理
        EventBus.user_message.disconnect(my_handler)

    def test_multiple_subscribers(self):
        """测试多个订阅者接收同一信号"""
        from services.event_bus import EventBus

        received_1 = []
        received_2 = []

        def handler_1(sender, **kwargs):
            received_1.append(kwargs)

        def handler_2(sender, **kwargs):
            received_2.append(kwargs)

        EventBus.user_message.connect(handler_1)
        EventBus.user_message.connect(handler_2)

        EventBus.emit('user_message', user_id=1, content="broadcast")

        assert len(received_1) == 1
        assert len(received_2) == 1
        assert received_1[0]['content'] == "broadcast"
        assert received_2[0]['content'] == "broadcast"

        # 清理
        EventBus.user_message.disconnect(handler_1)
        EventBus.user_message.disconnect(handler_2)


class TestEventBusSignalParameters:
    """测试信号参数传递"""

    def test_complex_parameters(self):
        """测试复杂参数传递"""
        from services.event_bus import EventBus

        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        EventBus.ai_response.connect(handler)

        complex_data = {
            'user_id': 1,
            'content': 'streaming chunk',
            'is_delta': True,
            'metadata': {
                'timestamp': '2024-01-01T00:00:00',
                'tokens': 10
            }
        }

        EventBus.emit('ai_response', **complex_data)

        assert len(received) == 1
        assert received[0]['user_id'] == 1
        assert received[0]['metadata']['tokens'] == 10

        # 清理
        EventBus.ai_response.disconnect(handler)

    def test_emit_nonexistent_signal_raises_error(self):
        """测试发射不存在的信号抛出错误"""
        from services.event_bus import EventBus

        with pytest.raises(AttributeError):
            EventBus.emit('nonexistent_signal')


class TestEventBusDisconnect:
    """测试信号断开连接"""

    def test_disconnect_handler(self):
        """测试断开连接后不再接收信号"""
        from services.event_bus import EventBus

        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        EventBus.user_message.connect(handler)

        # 第一次发射
        EventBus.emit('user_message', user_id=1, content="first")
        assert len(received) == 1

        # 断开连接
        EventBus.user_message.disconnect(handler)

        # 第二次发射
        EventBus.emit('user_message', user_id=2, content="second")
        assert len(received) == 1  # 仍然是 1，说明断开成功


class TestEventBusOffMethod:
    """测试 EventBus off 方法"""

    def test_off_method_disconnects_handler(self):
        """测试 off 方法正确断开处理器"""
        from services.event_bus import EventBus

        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        # 使用 on 装饰器连接
        EventBus.user_message.connect(handler)

        EventBus.emit('user_message', user_id=1, content="test1")
        assert len(received) == 1

        # 使用 off 方法断开
        EventBus.off('user_message', handler)

        EventBus.emit('user_message', user_id=2, content="test2")
        assert len(received) == 1  # 不应增加


class TestEventBusReturnType:
    """测试 EventBus 返回值"""

    def test_emit_returns_list_of_results(self):
        """测试 emit 返回处理器结果列表"""
        from services.event_bus import EventBus

        def handler(sender, **kwargs):
            return kwargs['user_id'] * 2

        EventBus.user_message.connect(handler)

        results = EventBus.user_message.send(None, user_id=5, content="test")

        # blinker send 返回 [(receiver, return_value), ...]
        assert len(results) == 1
        assert results[0][1] == 10  # 5 * 2

        # 清理
        EventBus.user_message.disconnect(handler)