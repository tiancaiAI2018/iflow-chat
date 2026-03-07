"""
iFlow SDK 封装服务测试
"""
import pytest
import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.iflow_client import (
    IFlowClientService,
    MessageType,
    ChatMessage,
    get_iflow_client,
    close_iflow_client,
)
from backend.config import settings


class TestChatMessage:
    """ChatMessage 数据类测试"""
    
    def test_text_message(self):
        """测试文本消息创建"""
        msg = ChatMessage(
            type=MessageType.TEXT,
            content="Hello",
            is_delta=True,
            is_finished=False,
        )
        assert msg.type == MessageType.TEXT
        assert msg.content == "Hello"
        assert msg.is_delta is True
        assert msg.is_finished is False
    
    def test_tool_call_message(self):
        """测试工具调用消息创建"""
        msg = ChatMessage(
            type=MessageType.TOOL_CALL,
            tool_name="get_weather",
            tool_arguments={"city": "Beijing"},
            tool_status="pending",
        )
        assert msg.type == MessageType.TOOL_CALL
        assert msg.tool_name == "get_weather"
        assert msg.tool_arguments == {"city": "Beijing"}
        assert msg.tool_status == "pending"
    
    def test_task_finish_message(self):
        """测试任务完成消息创建"""
        msg = ChatMessage(
            type=MessageType.TASK_FINISH,
            is_finished=True,
            stop_reason="end_turn",
        )
        assert msg.type == MessageType.TASK_FINISH
        assert msg.is_finished is True
        assert msg.stop_reason == "end_turn"
    
    def test_error_message(self):
        """测试错误消息创建"""
        msg = ChatMessage(
            type=MessageType.ERROR,
            content="Connection failed",
        )
        assert msg.type == MessageType.ERROR
        assert msg.content == "Connection failed"


class TestIFlowClientServiceInit:
    """IFlowClientService 初始化测试"""
    
    def test_default_init(self):
        """测试默认初始化"""
        client = IFlowClientService()
        assert client.cwd == "/root/.iflow-bot/workspace"
        assert client.timeout == 300.0
        assert client._client is None
        assert client._is_connected is False
    
    def test_custom_init(self):
        """测试自定义参数初始化"""
        client = IFlowClientService(
            cwd="/custom/path",
            timeout=60.0,
        )
        assert client.cwd == "/custom/path"
        assert client.timeout == 60.0

    # ============= feat-002: cwd 参数测试 =============

    def test_cwd_default_value(self):
        """测试 cwd 参数默认值"""
        client = IFlowClientService()
        assert client.cwd == "/root/.iflow-bot/workspace"

    def test_cwd_custom_value(self):
        """测试 cwd 参数自定义值"""
        custom_cwd = "/root/.iflow-bot/workspace/mybot"
        client = IFlowClientService(cwd=custom_cwd)
        assert client.cwd == custom_cwd

    def test_cwd_with_other_params(self):
        """测试 cwd 参数与其他参数组合"""
        client = IFlowClientService(
            cwd="/custom/path",
            timeout=120.0,
            session_id="test-session"
        )
        assert client.cwd == "/custom/path"
        assert client.timeout == 120.0
        assert client.session_id == "test-session"


class TestIFlowClientServiceConnection:
    """IFlowClientService 连接管理测试"""
    
    def setup_method(self):
        """每个测试方法前清理状态"""
        IFlowClientService._port_processes = {}
        IFlowClientService._user_ports = {}
        IFlowClientService._used_ports = set()
    
    def teardown_method(self):
        """每个测试方法后清理状态"""
        IFlowClientService._port_processes = {}
        IFlowClientService._user_ports = {}
        IFlowClientService._used_ports = set()
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """测试连接成功"""
        client = IFlowClientService()
        
        # Mock SDK client
        mock_sdk_client = AsyncMock()
        mock_sdk_client.__aenter__ = AsyncMock(return_value=mock_sdk_client)
        
        with patch('backend.services.iflow_client.SDKClient', return_value=mock_sdk_client):
            await client.connect()
            assert client.is_connected is True
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """测试重复连接"""
        client = IFlowClientService()
        client._is_connected = True
        client._client = MagicMock()
        
        # 不应该再次连接
        await client.connect()
        assert client.is_connected is True
    
    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """测试断开连接"""
        client = IFlowClientService()
        
        # Mock SDK client
        mock_sdk_client = AsyncMock()
        mock_sdk_client.__aexit__ = AsyncMock()
        
        client._client = mock_sdk_client
        client._is_connected = True
        
        await client.disconnect()
        assert client.is_connected is False
        assert client._client is None
    
    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        """测试未连接时断开"""
        client = IFlowClientService()
        
        # 应该不会抛出异常
        await client.disconnect()
        assert client.is_connected is False
    
    @pytest.mark.asyncio
    async def test_reconnect(self):
        """测试重新连接"""
        client = IFlowClientService()
        
        # Mock SDK client
        mock_sdk_client = AsyncMock()
        mock_sdk_client.__aenter__ = AsyncMock(return_value=mock_sdk_client)
        mock_sdk_client.__aexit__ = AsyncMock()
        
        with patch('backend.services.iflow_client.SDKClient', return_value=mock_sdk_client):
            # 先连接
            await client.connect()
            assert client.is_connected is True
            
            # 重新连接
            await client.reconnect()
            assert client.is_connected is True

    # ============= feat-002: auto_start_process 和 cwd 连接测试 =============

    @pytest.mark.asyncio
    async def test_connect_with_cwd_auto_start(self):
        """测试使用 cwd 和 auto_start_process=False 模式连接（手动管理 ACP 进程）"""
        custom_cwd = "/root/.iflow-bot/workspace/mybot"
        client = IFlowClientService(cwd=custom_cwd)
        
        # Mock SDK client
        mock_sdk_client = AsyncMock()
        mock_sdk_client.__aenter__ = AsyncMock(return_value=mock_sdk_client)
        mock_sdk_client._session_id = "test-session-123"
        
        # 捕获传递给 SDKClient 的 options
        captured_options = None
        
        def capture_options(options):
            nonlocal captured_options
            captured_options = options
            return mock_sdk_client
        
        with patch.object(IFlowClientService, '_start_acp_process', return_value=AsyncMock()):
            with patch('backend.services.iflow_client.SDKClient', side_effect=capture_options):
                await client.connect()
                
                # 验证 IFlowOptions 参数
                assert captured_options is not None
                assert captured_options.auto_start_process is False  # 关键：手动管理
                assert captured_options.cwd == custom_cwd
    
    @pytest.mark.asyncio
    async def test_connect_options_no_url(self):
        """测试连接时 IFlowOptions 使用动态分配的 url 和 auto_start_process=False"""
        client = IFlowClientService(cwd="/root/.iflow-bot/workspace/mybot")
        
        # Mock SDK client
        mock_sdk_client = AsyncMock()
        mock_sdk_client.__aenter__ = AsyncMock(return_value=mock_sdk_client)
        
        # 捕获传递给 SDKClient 的 options
        captured_options = None
        
        def capture_options(options):
            nonlocal captured_options
            captured_options = options
            return mock_sdk_client
        
        with patch.object(IFlowClientService, '_start_acp_process', return_value=AsyncMock()):
            with patch('backend.services.iflow_client.SDKClient', side_effect=capture_options):
                await client.connect()
                
                # 验证 IFlowOptions 参数
                assert captured_options is not None
                assert captured_options.cwd == "/root/.iflow-bot/workspace/mybot"
                # auto_start_process 应该为 False（手动管理 ACP 进程）
                assert captured_options.auto_start_process is False
                # URL 应该是动态分配的端口
                assert captured_options.url.startswith("ws://localhost:")
                assert "/acp" in captured_options.url

    @pytest.mark.asyncio
    async def test_connect_with_session_id(self):
        """测试连接时传递 session_id"""
        client = IFlowClientService(
            cwd="/root/.iflow-bot/workspace/mybot",
            session_id="existing-session-456"
        )
        
        # Mock SDK client
        mock_sdk_client = AsyncMock()
        mock_sdk_client.__aenter__ = AsyncMock(return_value=mock_sdk_client)
        
        # 捕获传递给 SDKClient 的 options
        captured_options = None
        
        def capture_options(options):
            nonlocal captured_options
            captured_options = options
            return mock_sdk_client
        
        with patch.object(IFlowClientService, '_start_acp_process', return_value=AsyncMock()):
            with patch('backend.services.iflow_client.SDKClient', side_effect=capture_options):
                await client.connect()
                
                # 验证 IFlowOptions 包含 session_id
                assert captured_options is not None
                assert captured_options.session_id == "existing-session-456"


class TestIFlowClientServiceQuery:
    """IFlowClientService 查询测试"""
    
    @pytest.mark.asyncio
    async def test_query_stream_text_messages(self):
        """测试流式查询文本消息"""
        client = IFlowClientService()
        
        # Mock SDK client 和消息
        mock_sdk_client = AsyncMock()
        mock_sdk_client.send_message = AsyncMock()
        
        # 创建模拟消息
        from iflow_sdk import AssistantMessage, TaskFinishMessage, StopReason
        
        mock_chunk = MagicMock()
        mock_chunk.text = "Hello"
        
        text_msg = MagicMock(spec=AssistantMessage)
        text_msg.chunk = mock_chunk
        
        finish_msg = MagicMock(spec=TaskFinishMessage)
        finish_msg.stop_reason = StopReason.END_TURN
        
        mock_sdk_client.receive_messages = MagicMock(
            return_value=self._async_generator([text_msg, finish_msg])
        )
        
        client._client = mock_sdk_client
        client._is_connected = True
        
        messages = []
        async for msg in client.query_stream("test"):
            messages.append(msg)
        
        # 验证消息
        text_messages = [m for m in messages if m.type == MessageType.TEXT]
        assert len(text_messages) >= 1
        assert text_messages[0].content == "Hello"
        assert text_messages[0].is_delta is True
    
    @pytest.mark.asyncio
    async def test_query_stream_tool_call(self):
        """测试流式查询工具调用"""
        client = IFlowClientService()
        
        # Mock SDK client
        mock_sdk_client = AsyncMock()
        mock_sdk_client.send_message = AsyncMock()
        
        # 创建模拟工具调用消息
        from iflow_sdk import ToolCallMessage, ToolCallStatus, TaskFinishMessage, StopReason
        
        tool_msg = MagicMock(spec=ToolCallMessage)
        tool_msg.tool_name = "get_weather"
        tool_msg.arguments = {"city": "Beijing"}
        tool_msg.status = ToolCallStatus.COMPLETED
        tool_msg.result = {"temp": 25}
        tool_msg.error = None
        
        finish_msg = MagicMock(spec=TaskFinishMessage)
        finish_msg.stop_reason = StopReason.END_TURN
        
        mock_sdk_client.receive_messages = MagicMock(
            return_value=self._async_generator([tool_msg, finish_msg])
        )
        
        client._client = mock_sdk_client
        client._is_connected = True
        
        tool_calls = []
        async for msg in client.query_stream("test"):
            if msg.type == MessageType.TOOL_CALL:
                tool_calls.append(msg)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "get_weather"
        assert tool_calls[0].tool_status == "completed"
        assert tool_calls[0].tool_result == {"temp": 25}
    
    @pytest.mark.asyncio
    async def test_query_stream_not_connected(self):
        """测试未连接时查询"""
        client = IFlowClientService()
        
        # Mock connect 方法
        client.connect = AsyncMock()
        
        messages = []
        async for msg in client.query_stream("test"):
            messages.append(msg)
        
        # 应该尝试连接
        client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_query_sync(self):
        """测试同步查询"""
        client = IFlowClientService()
        
        # Mock query_stream
        async def mock_stream(*args):
            yield ChatMessage(type=MessageType.TEXT, content="Hello ", is_delta=True)
            yield ChatMessage(type=MessageType.TEXT, content="World", is_delta=True)
            yield ChatMessage(type=MessageType.TEXT, content="", is_finished=True)
        
        client.query_stream = mock_stream
        
        result = await client.query("test")
        assert result == "Hello World"
    
    @pytest.mark.asyncio
    async def test_query_stream_with_callback(self):
        """测试带回调的流式查询"""
        client = IFlowClientService()
        
        # Mock SDK client
        mock_sdk_client = AsyncMock()
        mock_sdk_client.send_message = AsyncMock()
        
        from iflow_sdk import ToolCallMessage, ToolCallStatus, TaskFinishMessage, StopReason
        
        tool_msg = MagicMock(spec=ToolCallMessage)
        tool_msg.tool_name = "test_tool"
        tool_msg.arguments = {}
        tool_msg.status = ToolCallStatus.PENDING
        tool_msg.result = None
        tool_msg.error = None
        
        finish_msg = MagicMock(spec=TaskFinishMessage)
        finish_msg.stop_reason = StopReason.END_TURN
        
        mock_sdk_client.receive_messages = MagicMock(
            return_value=self._async_generator([tool_msg, finish_msg])
        )
        
        client._client = mock_sdk_client
        client._is_connected = True
        
        callback_calls = []
        
        def on_tool_call(msg):
            callback_calls.append(msg)
        
        async for msg in client.query_stream("test", on_tool_call=on_tool_call):
            pass
        
        assert len(callback_calls) == 1
        assert callback_calls[0].tool_name == "test_tool"
    
    def _async_generator(self, items):
        """辅助方法：创建异步生成器"""
        async def gen():
            for item in items:
                yield item
        return gen()


class TestParseToolCall:
    """工具调用解析测试"""
    
    def test_parse_pending_status(self):
        """测试解析 pending 状态"""
        from iflow_sdk import ToolCallStatus
        
        client = IFlowClientService()
        msg = MagicMock()
        msg.tool_name = "test_tool"
        msg.arguments = {"arg": "value"}
        msg.status = ToolCallStatus.PENDING
        msg.result = None
        msg.error = None
        
        result = client._parse_tool_call(msg)
        
        assert result.type == MessageType.TOOL_CALL
        assert result.tool_name == "test_tool"
        assert result.tool_status == "pending"
        assert result.tool_result is None
    
    def test_parse_completed_status(self):
        """测试解析 completed 状态"""
        from iflow_sdk import ToolCallStatus
        
        client = IFlowClientService()
        msg = MagicMock()
        msg.tool_name = "test_tool"
        msg.arguments = {}
        msg.status = ToolCallStatus.COMPLETED
        msg.result = {"data": "success"}
        msg.error = None
        
        result = client._parse_tool_call(msg)
        
        assert result.tool_status == "completed"
        assert result.tool_result == {"data": "success"}
    
    def test_parse_failed_status(self):
        """测试解析 failed 状态"""
        from iflow_sdk import ToolCallStatus
        
        client = IFlowClientService()
        msg = MagicMock()
        msg.tool_name = "test_tool"
        msg.arguments = {}
        msg.status = ToolCallStatus.FAILED
        msg.result = None
        msg.error = "Something went wrong"
        
        result = client._parse_tool_call(msg)
        
        assert result.tool_status == "failed"
        assert result.tool_error == "Something went wrong"


class TestContextManager:
    """上下文管理器测试"""
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试异步上下文管理器"""
        client = IFlowClientService()
        
        # Mock connect 和 disconnect
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        
        async with client as c:
            assert c is client
            client.connect.assert_called_once()
        
        client.disconnect.assert_called_once()


class TestGlobalClient:
    """全局客户端测试"""
    
    @pytest.mark.asyncio
    async def test_get_iflow_client(self):
        """测试获取全局客户端"""
        from backend.services.iflow_client import _global_client
        
        # 重置全局客户端
        import backend.services.iflow_client
        backend.services.iflow_client._global_client = None
        
        client = await get_iflow_client()
        assert client is not None
        assert isinstance(client, IFlowClientService)
        
        # 再次获取应该是同一个实例
        client2 = await get_iflow_client()
        assert client is client2
    
    @pytest.mark.asyncio
    async def test_close_iflow_client(self):
        """测试关闭全局客户端"""
        import backend.services.iflow_client
        
        # 先获取客户端
        client = await get_iflow_client()
        client.disconnect = AsyncMock()
        
        # 关闭
        await close_iflow_client()
        
        assert backend.services.iflow_client._global_client is None


class TestErrorMessage:
    """错误消息处理测试"""
    
    @pytest.mark.asyncio
    async def test_query_stream_error(self):
        """测试查询流式错误 - 当客户端对象为 None 时返回错误"""
        client = IFlowClientService()
        
        # Mock connect 方法，使其不尝试真正连接
        client.connect = AsyncMock()
        client._client = None  # 模拟连接后客户端仍为 None
        
        messages = []
        async for msg in client.query_stream("test"):
            messages.append(msg)
        
        assert len(messages) == 1
        assert messages[0].type == MessageType.ERROR
        assert "Not connected" in messages[0].content
    
    @pytest.mark.asyncio
    async def test_query_stream_timeout(self):
        """测试查询超时"""
        client = IFlowClientService()
        
        # Mock SDK client
        mock_sdk_client = AsyncMock()
        mock_sdk_client.send_message = AsyncMock()
        
        # 创建会超时的消息生成器
        async def timeout_gen():
            raise asyncio.TimeoutError()
            yield  # 使其成为生成器
        
        mock_sdk_client.receive_messages = MagicMock(return_value=timeout_gen())
        
        client._client = mock_sdk_client
        client._is_connected = True
        
        messages = []
        async for msg in client.query_stream("test"):
            messages.append(msg)
        
        error_messages = [m for m in messages if m.type == MessageType.ERROR]
        assert len(error_messages) >= 1
        assert "timeout" in error_messages[0].content.lower()


class TestIsConnected:
    """连接状态测试"""
    
    def test_is_connected_true(self):
        """测试连接状态为 True"""
        client = IFlowClientService()
        client._client = MagicMock()
        client._is_connected = True
        
        assert client.is_connected is True
    
    def test_is_connected_false_no_client(self):
        """测试连接状态为 False（无客户端）"""
        client = IFlowClientService()
        client._is_connected = True
        client._client = None
        
        assert client.is_connected is False
    
    def test_is_connected_false_not_connected(self):
        """测试连接状态为 False（未连接）"""
        client = IFlowClientService()
        client._client = MagicMock()
        client._is_connected = False
        
        assert client.is_connected is False


# ============= feat-042: ACP 端口管理测试 =============

class TestACPPortManagement:
    """ACP 端口管理测试"""
    
    def setup_method(self):
        """每个测试方法前清理状态"""
        # 清理类属性状态
        IFlowClientService._port_processes = {}
        IFlowClientService._user_ports = {}
        IFlowClientService._used_ports = set()
    
    def teardown_method(self):
        """每个测试方法后清理状态"""
        # 清理类属性状态
        IFlowClientService._port_processes = {}
        IFlowClientService._user_ports = {}
        IFlowClientService._used_ports = set()
    
    def test_class_attributes_exist(self):
        """测试类属性存在性"""
        assert hasattr(IFlowClientService, '_port_processes')
        assert hasattr(IFlowClientService, '_user_ports')
        assert hasattr(IFlowClientService, '_used_ports')
        assert hasattr(IFlowClientService, '_lock')
        assert isinstance(IFlowClientService._lock, asyncio.Lock)
    
    def test_is_port_available_true(self):
        """测试端口可用检查 - 端口空闲"""
        # 使用一个不太可能被占用的端口
        port = 19999
        result = IFlowClientService._is_port_available(port)
        assert result is True
    
    def test_is_port_available_false(self):
        """测试端口可用检查 - 端口被占用"""
        # 创建一个临时 socket 占用端口
        test_port = 19998
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('localhost', test_port))
            s.listen(1)
            
            result = IFlowClientService._is_port_available(test_port)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_find_available_port_success(self):
        """测试查找可用端口 - 成功场景"""
        user_id = 123
        
        port = await IFlowClientService._find_available_port(user_id)
        
        # 验证端口在配置范围内
        assert settings.ACP_PORT_START <= port <= settings.ACP_PORT_END
        # 验证端口已标记为使用
        assert port in IFlowClientService._used_ports
    
    @pytest.mark.asyncio
    async def test_find_available_port_multiple_users(self):
        """测试查找可用端口 - 多个用户"""
        user1_id = 100
        user2_id = 200
        
        port1 = await IFlowClientService._find_available_port(user1_id)
        port2 = await IFlowClientService._find_available_port(user2_id)
        
        # 验证两个端口不同
        assert port1 != port2
        # 验证都在配置范围内
        assert settings.ACP_PORT_START <= port1 <= settings.ACP_PORT_END
        assert settings.ACP_PORT_START <= port2 <= settings.ACP_PORT_END
    
    @pytest.mark.asyncio
    async def test_find_available_port_exhausted(self):
        """测试查找可用端口 - 端口耗尽场景"""
        user_id = 999
        
        # 模拟所有端口都被占用
        original_used_ports = IFlowClientService._used_ports.copy()
        IFlowClientService._used_ports = set(range(settings.ACP_PORT_START, settings.ACP_PORT_END + 1))
        
        with pytest.raises(RuntimeError) as exc_info:
            await IFlowClientService._find_available_port(user_id)
        
        assert "系统繁忙" in str(exc_info.value)
        
        # 恢复状态
        IFlowClientService._used_ports = original_used_ports
    
    def test_push_user_port(self):
        """测试端口入栈"""
        user_id = 100
        port1 = 8091
        port2 = 8092
        
        # 入栈第一个端口
        IFlowClientService._push_user_port(user_id, port1)
        assert IFlowClientService._user_ports[user_id] == [8091]
        
        # 入栈第二个端口（应该在栈顶）
        IFlowClientService._push_user_port(user_id, port2)
        assert IFlowClientService._user_ports[user_id] == [8092, 8091]
    
    def test_get_user_ports(self):
        """测试获取用户端口栈"""
        user_id = 100
        port1 = 8091
        port2 = 8092
        
        # 空栈
        assert IFlowClientService._get_user_ports(user_id) == []
        
        # 入栈后
        IFlowClientService._push_user_port(user_id, port1)
        IFlowClientService._push_user_port(user_id, port2)
        
        ports = IFlowClientService._get_user_ports(user_id)
        assert ports == [8092, 8091]
    
    def test_pop_user_port(self):
        """测试端口出栈"""
        user_id = 100
        port1 = 8091
        port2 = 8092
        
        IFlowClientService._push_user_port(user_id, port1)
        IFlowClientService._push_user_port(user_id, port2)
        IFlowClientService._used_ports.add(port1)
        IFlowClientService._used_ports.add(port2)
        
        # 移除端口
        result = IFlowClientService._pop_user_port(user_id, port1)
        assert result is True
        assert IFlowClientService._user_ports[user_id] == [8092]
        assert port1 not in IFlowClientService._used_ports
        
        # 移除不存在的端口
        result = IFlowClientService._pop_user_port(user_id, 9999)
        assert result is False
    
    def test_remove_user_port(self):
        """测试移除用户端口"""
        user_id = 100
        port1 = 8091
        port2 = 8092
        
        IFlowClientService._push_user_port(user_id, port1)
        IFlowClientService._push_user_port(user_id, port2)
        IFlowClientService._used_ports.add(port1)
        IFlowClientService._used_ports.add(port2)
        
        # 移除端口
        IFlowClientService._remove_user_port(user_id, port1)
        assert IFlowClientService._user_ports[user_id] == [8092]
        assert port1 not in IFlowClientService._used_ports
        
        # 移除最后一个端口，栈应该被删除
        IFlowClientService._remove_user_port(user_id, port2)
        assert user_id not in IFlowClientService._user_ports
        assert port2 not in IFlowClientService._used_ports
    
    def test_port_stack_order(self):
        """测试端口栈顺序 - 栈顶为最新"""
        user_id = 100
        
        # 模拟多次连接
        IFlowClientService._push_user_port(user_id, 8091)
        IFlowClientService._push_user_port(user_id, 8092)
        IFlowClientService._push_user_port(user_id, 8093)
        
        ports = IFlowClientService._get_user_ports(user_id)
        # 栈顶（最新）应该在索引 0
        assert ports[0] == 8093
        assert ports[1] == 8092
        assert ports[2] == 8091


# ============= feat-043: ACP 进程管理测试 =============

class TestACPProcessManagement:
    """ACP 进程启动与停止测试"""
    
    def setup_method(self):
        """每个测试方法前清理状态"""
        IFlowClientService._port_processes = {}
        IFlowClientService._user_ports = {}
        IFlowClientService._used_ports = set()
    
    def teardown_method(self):
        """每个测试方法后清理状态"""
        IFlowClientService._port_processes = {}
        IFlowClientService._user_ports = {}
        IFlowClientService._used_ports = set()
    
    @pytest.mark.asyncio
    async def test_start_acp_process_success(self):
        """测试进程启动成功 - 带 --stream 参数"""
        port = 8095
        
        # Mock asyncio.create_subprocess_exec
        mock_process = AsyncMock()
        mock_process.pid = 12345
        mock_process.returncode = None  # 进程运行中
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(IFlowClientService, '_is_port_available', return_value=False):  # 端口已被占用表示进程启动成功
                process = await IFlowClientService._start_acp_process(port)
        
        # 验证进程已保存
        assert port in IFlowClientService._port_processes
        assert IFlowClientService._port_processes[port] == mock_process
        assert process == mock_process
    
    @pytest.mark.asyncio
    async def test_start_acp_process_timeout(self):
        """测试进程启动超时"""
        port = 8096
        
        # Mock asyncio.create_subprocess_exec
        mock_process = AsyncMock()
        mock_process.pid = 12346
        mock_process.returncode = None
        mock_process.terminate = AsyncMock()
        mock_process.kill = AsyncMock()
        mock_process.wait = AsyncMock()
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(IFlowClientService, '_is_port_available', return_value=True):  # 端口始终可用表示进程未启动成功
                with pytest.raises(TimeoutError) as exc_info:
                    await IFlowClientService._start_acp_process(port)
        
        assert "超时" in str(exc_info.value) or "timeout" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_stop_acp_process_graceful(self):
        """测试进程优雅终止"""
        port = 8097
        
        # 创建模拟进程
        mock_process = AsyncMock()
        mock_process.pid = 12347
        mock_process.returncode = None  # 进程运行中
        mock_process.wait = AsyncMock(return_value=0)  # 正常退出
        mock_process.terminate = AsyncMock()
        mock_process.kill = AsyncMock()
        
        # 添加进程到管理字典
        IFlowClientService._port_processes[port] = mock_process
        IFlowClientService._used_ports.add(port)
        
        await IFlowClientService._stop_acp_process(port)
        
        # 验证调用了 terminate
        mock_process.terminate.assert_called_once()
        # 验证调用了 wait
        mock_process.wait.assert_called_once()
        # 验证未调用 kill（优雅退出成功）
        mock_process.kill.assert_not_called()
        # 验证进程已从字典移除
        assert port not in IFlowClientService._port_processes
        assert port not in IFlowClientService._used_ports
    
    @pytest.mark.asyncio
    async def test_stop_acp_process_force_kill(self):
        """测试进程强制终止（优雅终止超时后）"""
        port = 8098
        
        # 创建模拟进程 - 不响应 terminate
        mock_process = AsyncMock()
        mock_process.pid = 12348
        mock_process.returncode = None  # 进程运行中
        # wait 第一次返回超时，第二次返回退出码（模拟强制 kill 后）
        mock_process.wait = AsyncMock(side_effect=[asyncio.TimeoutError(), 0])
        mock_process.terminate = AsyncMock()
        mock_process.kill = AsyncMock()
        
        # 添加进程到管理字典
        IFlowClientService._port_processes[port] = mock_process
        IFlowClientService._used_ports.add(port)
        
        await IFlowClientService._stop_acp_process(port)
        
        # 验证调用了 terminate
        mock_process.terminate.assert_called_once()
        # 验证调用了 kill
        mock_process.kill.assert_called_once()
        # 验证进程已从字典移除
        assert port not in IFlowClientService._port_processes
        assert port not in IFlowClientService._used_ports
    
    @pytest.mark.asyncio
    async def test_stop_acp_process_already_terminated(self):
        """测试停止已终止的进程"""
        port = 8099
        
        # 创建模拟进程 - 已经终止
        mock_process = AsyncMock()
        mock_process.pid = 12349
        mock_process.returncode = 0  # 进程已终止
        mock_process.terminate = AsyncMock()
        mock_process.kill = AsyncMock()
        mock_process.wait = AsyncMock(return_value=0)
        
        # 添加进程到管理字典
        IFlowClientService._port_processes[port] = mock_process
        IFlowClientService._used_ports.add(port)
        
        await IFlowClientService._stop_acp_process(port)
        
        # 验证未调用 terminate（进程已终止）
        mock_process.terminate.assert_not_called()
        mock_process.kill.assert_not_called()
        # 验证进程已从字典移除
        assert port not in IFlowClientService._port_processes
        assert port not in IFlowClientService._used_ports
    
    @pytest.mark.asyncio
    async def test_stop_acp_process_not_exist(self):
        """测试停止不存在的进程"""
        port = 8100
        
        # 该端口没有对应的进程
        assert port not in IFlowClientService._port_processes
        
        # 应该不会抛出异常
        await IFlowClientService._stop_acp_process(port)
        
        # 验证状态未改变
        assert port not in IFlowClientService._port_processes


# ============= feat-044: connect 方法改造测试 =============

class TestConnectFlow:
    """connect 方法改造测试 - 集成端口栈管理"""
    
    def setup_method(self):
        """每个测试方法前清理状态"""
        IFlowClientService._port_processes = {}
        IFlowClientService._user_ports = {}
        IFlowClientService._used_ports = set()
    
    def teardown_method(self):
        """每个测试方法后清理状态"""
        IFlowClientService._port_processes = {}
        IFlowClientService._user_ports = {}
        IFlowClientService._used_ports = set()
    
    @pytest.mark.asyncio
    async def test_connect_flow(self):
        """测试连接流程：分配端口、启动进程、端口入栈、SDK 连接"""
        user_id = 1001
        test_port = 8888  # 使用固定的测试端口
        
        # 创建服务实例
        client = IFlowClientService(user_id=user_id)
        
        # Mock _start_acp_process 和 SDKClient
        mock_process = AsyncMock()
        mock_process.pid = 12345
        
        mock_sdk_client = AsyncMock()
        mock_sdk_client.__aenter__ = AsyncMock(return_value=mock_sdk_client)
        mock_sdk_client._session_id = "test-session-001"
        
        captured_options = None
        
        def capture_options(options):
            nonlocal captured_options
            captured_options = options
            return mock_sdk_client
        
        # 模拟真实的 _find_available_port 行为：分配端口并添加到 _used_ports
        async def mock_find_port(user_id):
            IFlowClientService._used_ports.add(test_port)
            return test_port
        
        with patch.object(IFlowClientService, '_find_available_port', side_effect=mock_find_port):
            with patch.object(IFlowClientService, '_start_acp_process', return_value=mock_process):
                with patch('backend.services.iflow_client.SDKClient', side_effect=capture_options):
                    await client.connect()
        
        # 验证：端口已分配并添加到已使用集合
        assert client._port == test_port
        assert test_port in IFlowClientService._used_ports
        
        # 验证：端口已入栈
        user_ports = IFlowClientService._get_user_ports(user_id)
        assert test_port in user_ports
        assert user_ports[0] == test_port  # 栈顶是最新端口
        
        # 验证：SDK 连接使用了 auto_start_process=False
        assert captured_options is not None
        assert captured_options.auto_start_process is False
        assert captured_options.url == f"ws://localhost:{test_port}/acp"
        
        # 验证：连接状态
        assert client.is_connected is True
    
    @pytest.mark.asyncio
    async def test_multi_connect_stack(self):
        """测试同一用户多次连接时端口栈的变化"""
        user_id = 1002
        
        # 模拟三次连接
        ports = []
        for i in range(3):
            client = IFlowClientService(user_id=user_id)
            
            mock_process = AsyncMock()
            mock_process.pid = 12345 + i
            
            mock_sdk_client = AsyncMock()
            mock_sdk_client.__aenter__ = AsyncMock(return_value=mock_sdk_client)
            mock_sdk_client._session_id = f"test-session-{i}"
            
            with patch.object(IFlowClientService, '_start_acp_process', return_value=mock_process):
                with patch('backend.services.iflow_client.SDKClient', return_value=mock_sdk_client):
                    await client.connect()
            
            ports.append(client._port)
        
        # 验证：端口栈中有 3 个端口
        user_ports = IFlowClientService._get_user_ports(user_id)
        assert len(user_ports) == 3
        
        # 验证：栈顶（索引 0）是最新的端口
        assert user_ports[0] == ports[2]
        assert user_ports[1] == ports[1]
        assert user_ports[2] == ports[0]
    
    @pytest.mark.asyncio
    async def test_connect_with_auto_start_false(self):
        """测试 connect 方法使用 auto_start_process=False"""
        user_id = 1003
        client = IFlowClientService(user_id=user_id)
        
        mock_process = AsyncMock()
        mock_sdk_client = AsyncMock()
        mock_sdk_client.__aenter__ = AsyncMock(return_value=mock_sdk_client)
        
        captured_options = None
        
        def capture_options(options):
            nonlocal captured_options
            captured_options = options
            return mock_sdk_client
        
        with patch.object(IFlowClientService, '_start_acp_process', return_value=mock_process):
            with patch('backend.services.iflow_client.SDKClient', side_effect=capture_options):
                await client.connect()
        
        # 关键验证：auto_start_process=False
        assert captured_options is not None
        assert captured_options.auto_start_process is False
        assert captured_options.cwd == client.cwd


# ============= feat-045: 断开逻辑测试 =============

class TestDisconnectLogic:
    """TaskFinishMessage 断开逻辑测试"""
    
    def setup_method(self):
        """每个测试方法前清理状态"""
        IFlowClientService._port_processes = {}
        IFlowClientService._user_ports = {}
        IFlowClientService._used_ports = set()
    
    def teardown_method(self):
        """每个测试方法后清理状态"""
        IFlowClientService._port_processes = {}
        IFlowClientService._user_ports = {}
        IFlowClientService._used_ports = set()
    
    @pytest.mark.asyncio
    async def test_on_task_finish_single_port_no_disconnect(self):
        """测试栈长度=1时不断开 - 当前正在使用的连接"""
        user_id = 2001
        port = 8091
        
        # 设置用户只有一个端口
        IFlowClientService._push_user_port(user_id, port)
        IFlowClientService._used_ports.add(port)
        
        client = IFlowClientService(user_id=user_id)
        client._port = port
        
        # Mock _stop_acp_process
        with patch.object(IFlowClientService, '_stop_acp_process', new_callable=AsyncMock) as mock_stop:
            await client._on_task_finish()
            
            # 验证：栈长度为1，不应该调用 _stop_acp_process
            mock_stop.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_task_finish_stack_top_no_disconnect(self):
        """测试栈长度>1且当前端口是栈顶时不断开"""
        user_id = 2002
        port1 = 8091
        port2 = 8092
        
        # 设置用户有两个端口，port2 在栈顶
        IFlowClientService._push_user_port(user_id, port1)  # 先入栈 port1
        IFlowClientService._push_user_port(user_id, port2)  # 再入栈 port2（栈顶）
        IFlowClientService._used_ports.add(port1)
        IFlowClientService._used_ports.add(port2)
        
        # 当前客户端使用栈顶的 port2
        client = IFlowClientService(user_id=user_id)
        client._port = port2
        
        # Mock _stop_acp_process
        with patch.object(IFlowClientService, '_stop_acp_process', new_callable=AsyncMock) as mock_stop:
            await client._on_task_finish()
            
            # 验证：当前端口是栈顶，不应该调用 _stop_acp_process
            mock_stop.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_task_finish_not_stack_top_disconnect(self):
        """测试栈长度>1且当前端口不是栈顶时断开旧进程"""
        user_id = 2003
        port1 = 8091
        port2 = 8092
        
        # 设置用户有两个端口，port2 在栈顶
        IFlowClientService._push_user_port(user_id, port1)  # 先入栈 port1
        IFlowClientService._push_user_port(user_id, port2)  # 再入栈 port2（栈顶）
        IFlowClientService._used_ports.add(port1)
        IFlowClientService._used_ports.add(port2)
        
        # 当前客户端使用的是旧的 port1（不是栈顶）
        client = IFlowClientService(user_id=user_id)
        client._port = port1
        
        # Mock _stop_acp_process 和 _remove_user_port
        with patch.object(IFlowClientService, '_stop_acp_process', new_callable=AsyncMock) as mock_stop:
            with patch.object(IFlowClientService, '_remove_user_port') as mock_remove:
                await client._on_task_finish()
                
                # 验证：当前端口不是栈顶，应该调用 _stop_acp_process 和 _remove_user_port
                mock_stop.assert_called_once_with(port1)
                mock_remove.assert_called_once_with(user_id, port1)
    
    @pytest.mark.asyncio
    async def test_on_task_finish_multiple_ports_disconnect_old(self):
        """测试多端口场景下断开旧进程 - 3个端口时中间端口触发断开"""
        user_id = 2004
        port1 = 8091
        port2 = 8092
        port3 = 8093
        
        # 设置用户有三个端口，port3 在栈顶
        IFlowClientService._push_user_port(user_id, port1)
        IFlowClientService._push_user_port(user_id, port2)
        IFlowClientService._push_user_port(user_id, port3)  # 栈顶
        IFlowClientService._used_ports.add(port1)
        IFlowClientService._used_ports.add(port2)
        IFlowClientService._used_ports.add(port3)
        
        # 场景1：当前客户端使用 port1（最旧，不是栈顶）
        client1 = IFlowClientService(user_id=user_id)
        client1._port = port1
        
        with patch.object(IFlowClientService, '_stop_acp_process', new_callable=AsyncMock) as mock_stop:
            with patch.object(IFlowClientService, '_remove_user_port') as mock_remove:
                await client1._on_task_finish()
                
                # 验证：port1 应该被断开
                mock_stop.assert_called_once_with(port1)
                mock_remove.assert_called_once_with(user_id, port1)
        
        # 清理模拟调用
        mock_stop.reset_mock()
        mock_remove.reset_mock()
        
        # 场景2：当前客户端使用 port2（中间，不是栈顶）
        client2 = IFlowClientService(user_id=user_id)
        client2._port = port2
        
        with patch.object(IFlowClientService, '_stop_acp_process', new_callable=AsyncMock) as mock_stop:
            with patch.object(IFlowClientService, '_remove_user_port') as mock_remove:
                await client2._on_task_finish()
                
                # 验证：port2 应该被断开
                mock_stop.assert_called_once_with(port2)
                mock_remove.assert_called_once_with(user_id, port2)
        
        # 清理模拟调用
        mock_stop.reset_mock()
        mock_remove.reset_mock()
        
        # 场景3：当前客户端使用 port3（栈顶）
        client3 = IFlowClientService(user_id=user_id)
        client3._port = port3
        
        with patch.object(IFlowClientService, '_stop_acp_process', new_callable=AsyncMock) as mock_stop:
            with patch.object(IFlowClientService, '_remove_user_port') as mock_remove:
                await client3._on_task_finish()
                
                # 验证：port3 是栈顶，不应该被断开
                mock_stop.assert_not_called()
                mock_remove.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_query_stream_calls_on_task_finish(self):
        """测试 query_stream 在 TaskFinishMessage 时调用 _on_task_finish"""
        user_id = 2005
        port = 8094
        
        # 设置用户有一个端口
        IFlowClientService._push_user_port(user_id, port)
        IFlowClientService._used_ports.add(port)
        
        client = IFlowClientService(user_id=user_id)
        client._port = port
        
        # Mock SDK client
        mock_sdk_client = AsyncMock()
        mock_sdk_client.send_message = AsyncMock()
        
        from iflow_sdk import TaskFinishMessage, StopReason
        
        finish_msg = MagicMock(spec=TaskFinishMessage)
        finish_msg.stop_reason = StopReason.END_TURN
        
        mock_sdk_client.receive_messages = MagicMock(
            return_value=self._async_generator([finish_msg])
        )
        
        client._client = mock_sdk_client
        client._is_connected = True
        
        # Mock _on_task_finish
        with patch.object(client, '_on_task_finish', new_callable=AsyncMock) as mock_on_finish:
            async for msg in client.query_stream("test"):
                pass
            
            # 验证：TaskFinishMessage 到达时调用了 _on_task_finish
            mock_on_finish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_task_finish_no_port(self):
        """测试 _port 为 None 时的处理"""
        user_id = 2006
        
        client = IFlowClientService(user_id=user_id)
        client._port = None  # 没有端口
        
        # Mock _stop_acp_process
        with patch.object(IFlowClientService, '_stop_acp_process', new_callable=AsyncMock) as mock_stop:
            await client._on_task_finish()
            
            # 验证：_port 为 None 时，不应该调用 _stop_acp_process
            mock_stop.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_on_task_finish_no_user_ports(self):
        """测试用户端口栈为空时的处理"""
        user_id = 2007
        port = 8095
        
        client = IFlowClientService(user_id=user_id)
        client._port = port
        # 用户端口栈为空（没有调用 _push_user_port）
        
        # Mock _stop_acp_process
        with patch.object(IFlowClientService, '_stop_acp_process', new_callable=AsyncMock) as mock_stop:
            await client._on_task_finish()
            
            # 验证：端口栈为空时，不应该调用 _stop_acp_process
            mock_stop.assert_not_called()
    
    def _async_generator(self, items):
        """辅助方法：创建异步生成器"""
        async def gen():
            for item in items:
                yield item
        return gen()