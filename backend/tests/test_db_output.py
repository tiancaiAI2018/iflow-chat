"""
DBOutputHandler 单元测试

测试数据库输出处理器正确订阅 ai_complete 信号并保存消息到数据库。
"""
import sys
import os

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 添加项目根目录到 Python 路径（用于 backend.xxx 导入）
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from services.event_bus import EventBus


class TestDBOutputHandler:
    """DBOutputHandler 测试类"""

    def setup_method(self):
        """每个测试方法前清理信号订阅"""
        EventBus.ai_complete.receivers.clear()

    @pytest.mark.asyncio
    async def test_handler_initialization(self):
        """测试处理器初始化"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        handler = DBOutputHandler(db_session=mock_session)
        
        assert handler is not None
        assert handler.db_session == mock_session

    @pytest.mark.asyncio
    async def test_handler_with_session_factory(self):
        """测试使用会话工厂初始化"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_factory = MagicMock()
        handler = DBOutputHandler(db_session_factory=mock_factory)
        
        assert handler is not None
        assert handler.db_session_factory == mock_factory

    @pytest.mark.asyncio
    async def test_ai_complete_signal_saves_to_database(self):
        """测试 ai_complete 信号触发数据库保存"""
        from services.output_handlers.db_output import DBOutputHandler
        
        # 创建模拟的数据库会话
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        # 创建模拟的 ChatHistory 类
        mock_chat_history_class = MagicMock()
        mock_chat_history_instance = MagicMock()
        mock_chat_history_instance.id = 1
        mock_chat_history_class.return_value = mock_chat_history_instance
        
        # Patch backend.models.user.ChatHistory（与 db_output.py 中的导入路径匹配）
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            # 发射 ai_complete 信号
            EventBus.emit(
                'ai_complete',
                sender='iflow_client',
                user_id=123,
                content="AI response content",
                conversation_id=456
            )
            
            # 给异步处理器一些时间执行
            await asyncio.sleep(0.1)
            
            # 验证 ChatHistory 被正确调用
            mock_chat_history_class.assert_called_once()
            call_kwargs = mock_chat_history_class.call_args.kwargs
            assert call_kwargs['user_id'] == 123
            assert call_kwargs['role'] == 'assistant'
            assert call_kwargs['content'] == "AI response content"
            assert call_kwargs['conversation_id'] == 456

    @pytest.mark.asyncio
    async def test_ai_complete_without_conversation_id(self):
        """测试 ai_complete 信号支持无 conversation_id"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        mock_chat_history_instance = MagicMock()
        mock_chat_history_instance.id = 2
        mock_chat_history_class.return_value = mock_chat_history_instance
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            # 发射不带 conversation_id 的 ai_complete 信号
            EventBus.emit(
                'ai_complete',
                sender='iflow_client',
                user_id=1,
                content="test"
            )
            
            await asyncio.sleep(0.1)
            
            # 验证 conversation_id 为 None
            call_kwargs = mock_chat_history_class.call_args.kwargs
            assert call_kwargs['conversation_id'] is None

    @pytest.mark.asyncio
    async def test_ai_complete_with_metadata(self):
        """测试 ai_complete 信号支持 metadata（目前忽略但不报错）"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            # 发射带 metadata 的 ai_complete 信号
            EventBus.emit(
                'ai_complete',
                sender='iflow_client',
                user_id=1,
                content="test",
                metadata={'model': 'gpt-4', 'tokens': 100}
            )
            
            await asyncio.sleep(0.1)
            
            # 验证正常保存（metadata 被忽略但不影响保存）
            mock_chat_history_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_ai_complete_missing_user_id(self):
        """测试缺少 user_id 时不保存"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            # 发射缺少 user_id 的信号
            EventBus.emit(
                'ai_complete',
                sender='iflow_client',
                content="test"
            )
            
            await asyncio.sleep(0.1)
            
            # ChatHistory 不应该被调用
            mock_chat_history_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_disconnect_removes_subscriptions(self):
        """测试断开连接后取消订阅"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            # 断开连接
            handler.disconnect()
            
            # 发射信号
            EventBus.emit('ai_complete', user_id=1, content="test")
            
            await asyncio.sleep(0.1)
            
            # ChatHistory 不应该被调用
            mock_chat_history_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_method(self):
        """测试 close 方法"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            # 调用 close
            await handler.close()
            
            # 发射信号应该不触发
            EventBus.emit('ai_complete', user_id=1, content="test")
            
            await asyncio.sleep(0.1)
            
            mock_chat_history_class.assert_not_called()


class TestDBOutputHandlerEdgeCases:
    """边界场景测试"""

    def setup_method(self):
        """每个测试方法前清理信号订阅"""
        EventBus.ai_complete.receivers.clear()

    @pytest.mark.asyncio
    async def test_unicode_content(self):
        """测试处理 Unicode 内容"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            unicode_content = "你好世界 🌍 مرحبا"
            EventBus.emit('ai_complete', user_id=1, content=unicode_content)
            
            await asyncio.sleep(0.1)
            
            call_kwargs = mock_chat_history_class.call_args.kwargs
            assert call_kwargs['content'] == unicode_content

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """测试处理空内容"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            EventBus.emit('ai_complete', user_id=1, content="")
            
            await asyncio.sleep(0.1)
            
            call_kwargs = mock_chat_history_class.call_args.kwargs
            assert call_kwargs['content'] == ""

    @pytest.mark.asyncio
    async def test_long_content(self):
        """测试处理长内容"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            long_content = "a" * 10000
            EventBus.emit('ai_complete', user_id=1, content=long_content)
            
            await asyncio.sleep(0.1)
            
            call_kwargs = mock_chat_history_class.call_args.kwargs
            assert call_kwargs['content'] == long_content

    @pytest.mark.asyncio
    async def test_special_characters(self):
        """测试处理特殊字符"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            special_content = '<script>alert("xss")</script>\n\t\r```code```'
            EventBus.emit('ai_complete', user_id=1, content=special_content)
            
            await asyncio.sleep(0.1)
            
            call_kwargs = mock_chat_history_class.call_args.kwargs
            assert call_kwargs['content'] == special_content

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        """测试多个处理器实例"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session_1 = AsyncMock()
        mock_session_1.add = MagicMock()
        mock_session_1.commit = AsyncMock()
        mock_session_1.refresh = AsyncMock()
        
        mock_session_2 = AsyncMock()
        mock_session_2.add = MagicMock()
        mock_session_2.commit = AsyncMock()
        mock_session_2.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler_1 = DBOutputHandler(db_session=mock_session_1)
            handler_2 = DBOutputHandler(db_session=mock_session_2)
            
            EventBus.emit('ai_complete', user_id=1, content="test")
            
            await asyncio.sleep(0.1)
            
            # 两个处理器都应该收到信号（ChatHistory 被调用两次）
            assert mock_chat_history_class.call_count == 2

    @pytest.mark.asyncio
    async def test_created_at_timezone(self):
        """测试 created_at 使用 UTC 时区"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            EventBus.emit('ai_complete', user_id=1, content="test")
            
            await asyncio.sleep(0.1)
            
            call_kwargs = mock_chat_history_class.call_args.kwargs
            # 验证 created_at 是一个 datetime 对象
            assert 'created_at' in call_kwargs
            assert isinstance(call_kwargs['created_at'], datetime)

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """测试数据库错误处理"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock(side_effect=Exception("Database error"))
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            # 发射信号，即使数据库错误也不应该抛出异常
            EventBus.emit('ai_complete', user_id=1, content="test")
            
            await asyncio.sleep(0.1)
            
            # 验证尝试保存（即使失败）
            mock_chat_history_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_factory_usage(self):
        """测试使用会话工厂创建会话"""
        from services.output_handlers.db_output import DBOutputHandler
        
        # 创建模拟的会话工厂
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.close = AsyncMock()
        
        mock_factory = MagicMock(return_value=mock_session)
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session_factory=mock_factory)
            
            EventBus.emit('ai_complete', user_id=1, content="test")
            
            await asyncio.sleep(0.1)
            
            # 验证会话工厂被调用
            mock_factory.assert_called_once()
            # 验证会话被关闭
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_role_is_assistant(self):
        """测试保存的消息角色为 assistant"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            EventBus.emit('ai_complete', user_id=1, content="test")
            
            await asyncio.sleep(0.1)
            
            call_kwargs = mock_chat_history_class.call_args.kwargs
            assert call_kwargs['role'] == 'assistant'


class TestDBOutputHandlerIntegration:
    """集成测试（与 EventBus 集成）"""

    def setup_method(self):
        """每个测试方法前清理信号订阅"""
        EventBus.ai_complete.receivers.clear()

    @pytest.mark.asyncio
    async def test_event_bus_integration(self):
        """测试与 EventBus 的集成"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            # 使用 EventBus.emit 发射信号
            EventBus.emit('ai_complete', user_id=42, content="Integration test")
            
            await asyncio.sleep(0.1)
            
            # 验证处理器响应了信号
            mock_chat_history_class.assert_called_once()
            call_kwargs = mock_chat_history_class.call_args.kwargs
            assert call_kwargs['user_id'] == 42
            assert call_kwargs['content'] == "Integration test"

    @pytest.mark.asyncio
    async def test_multiple_consecutive_signals(self):
        """测试连续多个信号"""
        from services.output_handlers.db_output import DBOutputHandler
        
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_chat_history_class = MagicMock()
        
        with patch('backend.models.user.ChatHistory', mock_chat_history_class):
            handler = DBOutputHandler(db_session=mock_session)
            
            # 连续发射多个信号
            EventBus.emit('ai_complete', user_id=1, content="message 1")
            EventBus.emit('ai_complete', user_id=2, content="message 2")
            EventBus.emit('ai_complete', user_id=3, content="message 3")
            
            await asyncio.sleep(0.2)
            
            # 验证所有消息都被保存
            assert mock_chat_history_class.call_count == 3
