"""
main.py 应用启动测试

测试 Redis 连接初始化和处理器初始化是否正确。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


class TestAppLifespan:
    """应用生命周期测试"""

    def test_settings_has_redis_config(self):
        """测试配置包含 Redis 配置"""
        from backend.config import settings

        assert hasattr(settings, 'REDIS_URL')
        assert hasattr(settings, 'REDIS_MAX_MEMORY')
        assert hasattr(settings, 'REDIS_MESSAGE_TTL')
        assert settings.REDIS_URL == "redis://localhost:6379/0"
        assert settings.REDIS_MAX_MEMORY == "32mb"
        assert settings.REDIS_MESSAGE_TTL == 300

    def test_message_buffer_initialization(self):
        """测试 MessageBuffer 初始化"""
        from backend.services.message_buffer import MessageBuffer

        buffer = MessageBuffer("redis://localhost:6379/0", ttl=300)

        assert buffer.redis_url == "redis://localhost:6379/0"
        assert buffer.ttl == 300
        assert buffer._redis is None  # 懒加载

    def test_websocket_input_handler_initialization(self):
        """测试 WebSocketInputHandler 初始化"""
        from backend.services.input_handlers import WebSocketInputHandler

        # 无参数初始化
        handler = WebSocketInputHandler()
        assert handler.sender is None

        # 带 sender 初始化
        handler_with_sender = WebSocketInputHandler(sender='test_client')
        assert handler_with_sender.sender == 'test_client'

    def test_redis_output_handler_initialization(self):
        """测试 RedisOutputHandler 初始化"""
        from backend.services.output_handlers import RedisOutputHandler
        from backend.services.message_buffer import MessageBuffer

        buffer = MessageBuffer("redis://localhost:6379/0")
        handler = RedisOutputHandler(buffer=buffer)

        assert handler.buffer is buffer
        assert len(handler._subscribers) == 2  # ai_response, ai_complete

        # 清理
        handler.disconnect()

    def test_db_output_handler_initialization(self):
        """测试 DBOutputHandler 初始化"""
        from backend.services.output_handlers import DBOutputHandler

        # 无参数初始化
        handler = DBOutputHandler()
        assert handler.db_session is None
        assert handler.db_session_factory is None
        assert len(handler._subscribers) == 1  # ai_complete

        # 清理
        handler.disconnect()

    def test_db_output_handler_with_session_factory(self):
        """测试 DBOutputHandler 带会话工厂初始化"""
        from backend.services.output_handlers import DBOutputHandler

        mock_factory = MagicMock()
        handler = DBOutputHandler(db_session_factory=mock_factory)

        assert handler.db_session_factory is mock_factory
        assert handler.db_session is None

        # 清理
        handler.disconnect()

    def test_iflow_processor_initialization(self):
        """测试 IFlowProcessor 初始化"""
        from backend.services.iflow_processor import IFlowProcessor

        processor = IFlowProcessor()

        assert len(processor._sessions) == 0
        assert len(processor._subscribers) == 1  # user_message

        # 清理
        processor.disconnect()

    @pytest.mark.asyncio
    async def test_message_buffer_connect_and_close(self):
        """测试 MessageBuffer 连接和关闭"""
        from backend.services.message_buffer import MessageBuffer

        buffer = MessageBuffer("redis://localhost:6379/0")

        # 测试懒加载
        assert buffer._redis is None

        # 测试连接
        redis_client = buffer.redis
        assert redis_client is not None
        assert buffer._redis is not None

        # 测试关闭
        await buffer.close()
        assert buffer._redis is None

    @pytest.mark.asyncio
    async def test_iflow_processor_close(self):
        """测试 IFlowProcessor 关闭"""
        from backend.services.iflow_processor import IFlowProcessor

        processor = IFlowProcessor()
        await processor.close()

        # 验证订阅已断开
        assert len(processor._subscribers) == 0

    @pytest.mark.asyncio
    async def test_redis_output_handler_close(self):
        """测试 RedisOutputHandler 断开"""
        from backend.services.output_handlers import RedisOutputHandler
        from backend.services.message_buffer import MessageBuffer

        buffer = MessageBuffer("redis://localhost:6379/0")
        handler = RedisOutputHandler(buffer=buffer)

        # 断开订阅
        handler.disconnect()

        # 验证订阅已断开
        assert len(handler._subscribers) == 0

    @pytest.mark.asyncio
    async def test_db_output_handler_close(self):
        """测试 DBOutputHandler 断开"""
        from backend.services.output_handlers import DBOutputHandler

        handler = DBOutputHandler()
        handler.disconnect()

        # 验证订阅已断开
        assert len(handler._subscribers) == 0

        # 测试异步 close 方法
        handler2 = DBOutputHandler()
        await handler2.close()
        assert len(handler2._subscribers) == 0


class TestGlobalProcessorFunctions:
    """全局处理器函数测试"""

    def test_get_iflow_processor_singleton(self):
        """测试全局处理器单例"""
        from backend.services.iflow_processor import get_iflow_processor, close_iflow_processor, _global_processor
        import backend.services.iflow_processor as module

        # 重置全局实例
        module._global_processor = None

        # 获取实例
        processor1 = get_iflow_processor()
        processor2 = get_iflow_processor()

        assert processor1 is processor2

        # 清理
        processor1.disconnect()
        module._global_processor = None

    @pytest.mark.asyncio
    async def test_close_iflow_processor(self):
        """测试关闭全局处理器"""
        from backend.services.iflow_processor import get_iflow_processor, close_iflow_processor
        import backend.services.iflow_processor as module

        # 重置
        module._global_processor = None

        # 获取实例
        processor = get_iflow_processor()
        assert processor is not None

        # 关闭
        await close_iflow_processor()
        assert module._global_processor is None


class TestAppStartup:
    """应用启动集成测试"""

    @pytest.mark.asyncio
    async def test_redis_connection_available(self):
        """测试 Redis 连接可用"""
        from backend.services.message_buffer import MessageBuffer

        buffer = MessageBuffer("redis://localhost:6379/0")

        try:
            # 测试 ping
            await buffer.redis.ping()
            result = True
        except Exception as e:
            result = False
            print(f"Redis connection failed: {e}")
        finally:
            await buffer.close()

        assert result, "Redis connection should be available"

    @pytest.mark.asyncio
    async def test_full_initialization_flow(self):
        """测试完整初始化流程"""
        from backend.services.message_buffer import MessageBuffer
        from backend.services.input_handlers import WebSocketInputHandler
        from backend.services.output_handlers import RedisOutputHandler, DBOutputHandler
        from backend.services.iflow_processor import IFlowProcessor

        # 1. 初始化 MessageBuffer
        buffer = MessageBuffer("redis://localhost:6379/0")

        # 2. 初始化输入处理器
        input_handler = WebSocketInputHandler(sender='test')

        # 3. 初始化输出处理器
        redis_handler = RedisOutputHandler(buffer=buffer)
        db_handler = DBOutputHandler()

        # 4. 初始化 IFlowProcessor
        processor = IFlowProcessor()

        try:
            # 验证所有组件初始化成功
            assert buffer._redis is None  # 懒加载，未使用时不连接
            assert input_handler.sender == 'test'
            assert len(redis_handler._subscribers) == 2
            assert len(db_handler._subscribers) == 1
            assert len(processor._subscribers) == 1

        finally:
            # 清理
            redis_handler.disconnect()
            db_handler.disconnect()
            processor.disconnect()
            await buffer.close()

    @pytest.mark.asyncio
    async def test_event_bus_signal_flow(self):
        """测试 EventBus 信号流程"""
        from backend.services.event_bus import EventBus
        from backend.services.message_buffer import MessageBuffer
        from backend.services.output_handlers import RedisOutputHandler

        buffer = MessageBuffer("redis://localhost:6379/0")
        handler = RedisOutputHandler(buffer=buffer)

        received_signals = []

        # 添加测试订阅者
        @EventBus.on('ai_response')
        def test_subscriber(sender, **kwargs):
            received_signals.append(('ai_response', kwargs))
            return None

        try:
            # 发射信号
            EventBus.emit('ai_response', sender='test', user_id=1, content='test')

            # 等待异步任务完成
            await asyncio.sleep(0.1)

            # 验证信号被接收
            assert len(received_signals) > 0

        finally:
            handler.disconnect()
            EventBus.ai_response.disconnect(test_subscriber)
            await buffer.close()


class TestAppResources:
    """应用资源管理测试"""

    @pytest.mark.asyncio
    async def test_resource_cleanup(self):
        """测试资源清理"""
        from backend.services.message_buffer import MessageBuffer
        from backend.services.output_handlers import RedisOutputHandler, DBOutputHandler
        from backend.services.iflow_processor import IFlowProcessor

        # 创建多个资源
        buffer = MessageBuffer("redis://localhost:6379/0")
        redis_handler = RedisOutputHandler(buffer=buffer)
        db_handler = DBOutputHandler()
        processor = IFlowProcessor()

        # 清理所有资源
        redis_handler.disconnect()
        db_handler.disconnect()
        processor.disconnect()
        await buffer.close()

        # 验证清理完成
        assert len(redis_handler._subscribers) == 0
        assert len(db_handler._subscribers) == 0
        assert len(processor._subscribers) == 0
        assert buffer._redis is None

    @pytest.mark.asyncio
    async def test_context_manager_usage(self):
        """测试上下文管理器用法"""
        from backend.services.message_buffer import MessageBuffer

        async with MessageBuffer("redis://localhost:6379/0") as buffer:
            # 在上下文中使用（懒加载，访问 redis 属性触发连接）
            redis_client = buffer.redis
            assert redis_client is not None

        # 退出上下文后自动关闭
        assert buffer._redis is None
