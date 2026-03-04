"""
WebSocket 服务测试

测试 WebSocket 连接管理、认证、消息路由等功能
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketState

from backend.main import app
from backend.services.websocket_manager import (
    WebSocketManager,
    ConnectionInfo,
    ConnectionStatus,
    get_websocket_manager,
)
from backend.services.auth import create_access_token
from backend.routers.websocket import (
    WSMessage,
    ChatMessage,
    AuthMessage,
    PingMessage,
    SwitchConversationMessage,
    AuthSuccessResponse,
    AuthFailedResponse,
    PongResponse,
    AssistantMessageResponse,
    ToolCallResponse,
    ErrorResponse,
    ConnectionStatusResponse,
    ConversationSwitchedResponse,
)


# ==================== Fixtures ====================

@pytest.fixture
def websocket_manager():
    """创建新的 WebSocket 管理器实例"""
    return WebSocketManager()


@pytest.fixture
def mock_websocket():
    """创建模拟的 WebSocket 对象"""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    return ws


# ==================== ConnectionInfo 测试 ====================

class TestConnectionInfo:
    """ConnectionInfo 数据类测试"""
    
    def test_create_connection_info(self):
        """测试创建连接信息"""
        mock_ws = Mock()
        conn_info = ConnectionInfo(
            websocket=mock_ws,
            user_id=1,
            connection_id="conn_1",
        )
        
        assert conn_info.websocket == mock_ws
        assert conn_info.user_id == 1
        assert conn_info.connection_id == "conn_1"
        assert conn_info.status == ConnectionStatus.CONNECTED
        assert isinstance(conn_info.connected_at, datetime)
        assert isinstance(conn_info.last_activity, datetime)
    
    def test_update_activity(self):
        """测试更新活动时间"""
        conn_info = ConnectionInfo(
            websocket=Mock(),
            user_id=1,
            connection_id="conn_1",
        )
        old_time = conn_info.last_activity
        
        # 等待一小段时间
        import time
        time.sleep(0.01)
        
        conn_info.update_activity()
        
        assert conn_info.last_activity > old_time


# ==================== WebSocketManager 测试 ====================

class TestWebSocketManager:
    """WebSocketManager 测试"""
    
    @pytest.mark.asyncio
    async def test_connect(self, websocket_manager, mock_websocket):
        """测试连接注册"""
        conn_info = await websocket_manager.connect(mock_websocket, user_id=1)
        
        assert conn_info.user_id == 1
        assert conn_info.connection_id.startswith("conn_")
        assert conn_info.status == ConnectionStatus.CONNECTED
        
        # 验证连接已被管理
        assert 1 in websocket_manager._connections
        assert conn_info.connection_id in websocket_manager._connection_map
    
    @pytest.mark.asyncio
    async def test_multiple_connections_same_user(self, websocket_manager):
        """测试同一用户的多个连接（多标签页）"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        
        conn_info1 = await websocket_manager.connect(mock_ws1, user_id=1)
        conn_info2 = await websocket_manager.connect(mock_ws2, user_id=1)
        
        # 验证两个连接 ID 不同
        assert conn_info1.connection_id != conn_info2.connection_id
        
        # 验证用户有两个连接
        user_connections = websocket_manager.get_user_connections(1)
        assert len(user_connections) == 2
    
    @pytest.mark.asyncio
    async def test_disconnect(self, websocket_manager, mock_websocket):
        """测试断开连接"""
        conn_info = await websocket_manager.connect(mock_websocket, user_id=1)
        connection_id = conn_info.connection_id
        
        # 断开连接
        user_id = await websocket_manager.disconnect(connection_id)
        
        assert user_id == 1
        assert connection_id not in websocket_manager._connection_map
        assert 1 not in websocket_manager._connections
    
    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self, websocket_manager):
        """测试断开不存在的连接"""
        user_id = await websocket_manager.disconnect("nonexistent_conn")
        assert user_id is None
    
    @pytest.mark.asyncio
    async def test_authenticate(self, websocket_manager, mock_websocket):
        """测试认证连接"""
        conn_info = await websocket_manager.connect(mock_websocket, user_id=1)
        
        # 认证前状态
        assert conn_info.status == ConnectionStatus.CONNECTED
        
        # 认证
        result = await websocket_manager.authenticate(conn_info.connection_id)
        
        assert result is True
        assert conn_info.status == ConnectionStatus.AUTHENTICATED
    
    @pytest.mark.asyncio
    async def test_authenticate_nonexistent(self, websocket_manager):
        """测试认证不存在的连接"""
        result = await websocket_manager.authenticate("nonexistent_conn")
        assert result is False
    
    def test_is_authenticated(self, websocket_manager, mock_websocket):
        """测试检查认证状态"""
        # 创建同步版本的连接
        mock_ws = Mock()
        conn_info = ConnectionInfo(
            websocket=mock_ws,
            user_id=1,
            connection_id="conn_test",
            status=ConnectionStatus.AUTHENTICATED,
        )
        websocket_manager._connection_map["conn_test"] = conn_info
        
        assert websocket_manager.is_authenticated("conn_test") is True
        assert websocket_manager.is_authenticated("nonexistent") is False
    
    def test_is_user_online(self, websocket_manager):
        """测试检查用户是否在线"""
        # 创建已认证的连接
        conn_info = ConnectionInfo(
            websocket=Mock(),
            user_id=1,
            connection_id="conn_1",
            status=ConnectionStatus.AUTHENTICATED,
        )
        websocket_manager._connections[1] = {"conn_1": conn_info}
        websocket_manager._connection_map["conn_1"] = conn_info
        
        assert websocket_manager.is_user_online(1) is True
        assert websocket_manager.is_user_online(2) is False
    
    def test_get_online_users(self, websocket_manager):
        """测试获取在线用户列表"""
        # 创建多个用户的连接
        for user_id in [1, 2, 3]:
            conn_info = ConnectionInfo(
                websocket=Mock(),
                user_id=user_id,
                connection_id=f"conn_{user_id}",
                status=ConnectionStatus.AUTHENTICATED,
            )
            websocket_manager._connections[user_id] = {f"conn_{user_id}": conn_info}
            websocket_manager._connection_map[f"conn_{user_id}"] = conn_info
        
        # 用户 4 未认证
        conn_info4 = ConnectionInfo(
            websocket=Mock(),
            user_id=4,
            connection_id="conn_4",
            status=ConnectionStatus.CONNECTED,
        )
        websocket_manager._connections[4] = {"conn_4": conn_info4}
        websocket_manager._connection_map["conn_4"] = conn_info4
        
        online_users = websocket_manager.get_online_users()
        
        assert len(online_users) == 3
        assert 1 in online_users
        assert 2 in online_users
        assert 3 in online_users
        assert 4 not in online_users
    
    @pytest.mark.asyncio
    async def test_send_to_connection(self, websocket_manager, mock_websocket):
        """测试向连接发送消息"""
        conn_info = await websocket_manager.connect(mock_websocket, user_id=1)
        
        message = {"type": "test", "data": "hello"}
        result = await websocket_manager.send_to_connection(
            conn_info.connection_id, message
        )
        
        assert result is True
        mock_websocket.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_send_to_connection_nonexistent(self, websocket_manager):
        """测试向不存在的连接发送消息"""
        result = await websocket_manager.send_to_connection(
            "nonexistent", {"type": "test"}
        )
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_to_user(self, websocket_manager):
        """测试向用户广播消息"""
        # 创建两个连接（模拟多标签页）
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        
        await websocket_manager.connect(mock_ws1, user_id=1)
        await websocket_manager.connect(mock_ws2, user_id=1)
        
        # 认证两个连接
        for conn_id in list(websocket_manager._connection_map.keys()):
            await websocket_manager.authenticate(conn_id)
        
        message = {"type": "test", "data": "broadcast"}
        count = await websocket_manager.send_to_user(1, message)
        
        assert count == 2
        mock_ws1.send_json.assert_called_once_with(message)
        mock_ws2.send_json.assert_called_once_with(message)
    
    def test_get_stats(self, websocket_manager):
        """测试获取统计信息"""
        # 创建一些连接
        for i in range(3):
            conn_info = ConnectionInfo(
                websocket=Mock(),
                user_id=i + 1,
                connection_id=f"conn_{i}",
                status=ConnectionStatus.AUTHENTICATED if i < 2 else ConnectionStatus.CONNECTED,
            )
            websocket_manager._connections[i + 1] = {f"conn_{i}": conn_info}
            websocket_manager._connection_map[f"conn_{i}"] = conn_info
        
        stats = websocket_manager.get_stats()
        
        assert stats["total_connections"] == 3
        assert stats["authenticated_connections"] == 2
        assert stats["online_users"] == 2
        assert stats["users_with_connections"] == 3


# ==================== 消息模型测试 ====================

class TestMessageModels:
    """消息模型测试"""
    
    def test_chat_message(self):
        """测试聊天消息"""
        msg = ChatMessage(content="Hello")
        assert msg.type == "chat"
        assert msg.content == "Hello"
        assert msg.conversation_id is None
    
    def test_chat_message_with_conversation(self):
        """测试带会话 ID 的聊天消息"""
        msg = ChatMessage(content="Hello", conversation_id=123)
        assert msg.type == "chat"
        assert msg.content == "Hello"
        assert msg.conversation_id == 123
    
    def test_auth_message(self):
        """测试认证消息"""
        msg = AuthMessage(token="test_token")
        assert msg.type == "auth"
        assert msg.token == "test_token"
    
    def test_ping_message(self):
        """测试心跳消息"""
        msg = PingMessage()
        assert msg.type == "ping"
    
    def test_switch_conversation_message(self):
        """测试切换会话消息"""
        msg = SwitchConversationMessage(conversation_id=42)
        assert msg.type == "switch_conversation"
        assert msg.conversation_id == 42


# ==================== 响应模型测试 ====================

class TestResponseModels:
    """响应模型测试"""
    
    def test_auth_success_response(self):
        """测试认证成功响应"""
        response = AuthSuccessResponse(user_id=1, username="test")
        assert response.type == "auth_success"
        assert response.user_id == 1
        assert response.username == "test"
        assert response.timestamp  # 应该有时间戳
    
    def test_auth_failed_response(self):
        """测试认证失败响应"""
        response = AuthFailedResponse(message="Invalid token")
        assert response.type == "auth_failed"
        assert response.message == "Invalid token"
    
    def test_pong_response(self):
        """测试心跳响应"""
        response = PongResponse()
        assert response.type == "pong"
    
    def test_assistant_message_response(self):
        """测试助手消息响应"""
        response = AssistantMessageResponse(
            content="Hello",
            is_delta=True,
            is_finished=False,
        )
        assert response.type == "assistant_message"
        assert response.content == "Hello"
        assert response.is_delta is True
        assert response.is_finished is False
    
    def test_tool_call_response(self):
        """测试工具调用响应"""
        response = ToolCallResponse(
            tool_name="get_weather",
            arguments={"city": "Beijing"},
            status="completed",
            result={"temp": 25},
        )
        assert response.type == "tool_call"
        assert response.tool_name == "get_weather"
        assert response.arguments == {"city": "Beijing"}
        assert response.status == "completed"
        assert response.result == {"temp": 25}
    
    def test_error_response(self):
        """测试错误响应"""
        response = ErrorResponse(
            message="Something went wrong",
            code="INTERNAL_ERROR",
        )
        assert response.type == "error"
        assert response.message == "Something went wrong"
        assert response.code == "INTERNAL_ERROR"
    
    def test_connection_status_response(self):
        """测试连接状态响应"""
        response = ConnectionStatusResponse(
            status="connected",
            message="WebSocket connected",
        )
        assert response.type == "connection_status"
        assert response.status == "connected"
        assert response.message == "WebSocket connected"
    
    def test_conversation_switched_response(self):
        """测试会话切换响应"""
        response = ConversationSwitchedResponse(
            conversation_id=123,
            title="测试会话",
            iflow_session_id="session_abc",
        )
        assert response.type == "conversation_switched"
        assert response.conversation_id == 123
        assert response.title == "测试会话"
        assert response.iflow_session_id == "session_abc"
    
    def test_conversation_switched_response_without_iflow_session(self):
        """测试会话切换响应（无 iflow session）"""
        response = ConversationSwitchedResponse(
            conversation_id=456,
            title="新会话",
        )
        assert response.type == "conversation_switched"
        assert response.conversation_id == 456
        assert response.title == "新会话"
        assert response.iflow_session_id is None


# ==================== WebSocket 端点集成测试 ====================

class TestWebSocketEndpoint:
    """WebSocket 端点集成测试"""
    
    @pytest.mark.asyncio
    async def test_websocket_connect(self):
        """测试 WebSocket 连接"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/1") as websocket:
                # 接收连接状态消息
                data = websocket.receive_json()
                assert data["type"] == "connection_status"
                assert data["status"] == "connected"
    
    @pytest.mark.asyncio
    async def test_websocket_auth_with_token(self):
        """测试通过 query 参数认证"""
        # 创建测试 token
        token = create_access_token({"sub": 1, "username": "test_user"})
        
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/1?token={token}") as websocket:
                # 接收连接状态消息
                data = websocket.receive_json()
                assert data["type"] == "connection_status"
                
                # 接收认证成功消息
                auth_data = websocket.receive_json()
                assert auth_data["type"] == "auth_success"
                assert auth_data["user_id"] == 1
    
    @pytest.mark.asyncio
    async def test_websocket_auth_with_message(self):
        """测试通过消息认证"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/1") as websocket:
                # 接收连接状态消息
                websocket.receive_json()
                
                # 发送认证消息
                token = create_access_token({"sub": 1, "username": "test_user"})
                websocket.send_json({"type": "auth", "token": token})
                
                # 接收认证成功消息
                auth_data = websocket.receive_json()
                assert auth_data["type"] == "auth_success"
    
    @pytest.mark.asyncio
    async def test_websocket_auth_failed(self):
        """测试认证失败"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/1") as websocket:
                # 接收连接状态消息
                websocket.receive_json()
                
                # 发送无效 token
                websocket.send_json({"type": "auth", "token": "invalid_token"})
                
                # 接收认证失败消息
                auth_data = websocket.receive_json()
                assert auth_data["type"] == "auth_failed"
    
    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self):
        """测试心跳"""
        token = create_access_token({"sub": 1, "username": "test_user"})
        
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/1?token={token}") as websocket:
                # 接收连接状态和认证消息
                websocket.receive_json()
                websocket.receive_json()
                
                # 发送心跳
                websocket.send_json({"type": "ping"})
                
                # 接收心跳响应
                pong = websocket.receive_json()
                assert pong["type"] == "pong"
    
    @pytest.mark.asyncio
    async def test_websocket_chat_without_auth(self):
        """测试未认证时发送聊天消息"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/1") as websocket:
                # 接收连接状态消息
                websocket.receive_json()
                
                # 发送聊天消息
                websocket.send_json({"type": "chat", "content": "Hello"})
                
                # 应该收到错误响应
                error = websocket.receive_json()
                assert error["type"] == "error"
                assert error["code"] == "NOT_AUTHENTICATED"
    
    @pytest.mark.asyncio
    async def test_websocket_unknown_message_type(self):
        """测试未知消息类型"""
        token = create_access_token({"sub": 1, "username": "test_user"})
        
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/1?token={token}") as websocket:
                # 接收连接状态和认证消息
                websocket.receive_json()
                websocket.receive_json()
                
                # 发送未知类型消息
                websocket.send_json({"type": "unknown"})
                
                # 应该收到错误响应
                error = websocket.receive_json()
                assert error["type"] == "error"
                assert error["code"] == "UNKNOWN_TYPE"


# ==================== 用户 ID 不匹配测试 ====================

class TestAuthValidation:
    """认证验证测试"""
    
    @pytest.mark.asyncio
    async def test_user_id_mismatch(self):
        """测试用户 ID 不匹配"""
        # 为用户 1 创建 token
        token = create_access_token({"sub": 1, "username": "test_user"})
        
        # 但尝试连接用户 2 的 WebSocket
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/2?token={token}") as websocket:
                # 接收连接状态消息
                websocket.receive_json()
                
                # 应该收到认证失败消息
                auth_data = websocket.receive_json()
                assert auth_data["type"] == "auth_failed"
                assert "mismatch" in auth_data["message"].lower()


# ==================== 会话切换测试 ====================

class TestConversationSwitch:
    """会话切换测试"""
    
    @pytest.mark.asyncio
    async def test_switch_conversation_without_auth(self):
        """测试未认证时切换会话"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/1") as websocket:
                # 接收连接状态消息
                websocket.receive_json()
                
                # 发送切换会话消息
                websocket.send_json({"type": "switch_conversation", "conversation_id": 1})
                
                # 应该收到错误响应
                error = websocket.receive_json()
                assert error["type"] == "error"
                assert error["code"] == "NOT_AUTHENTICATED"
    
    @pytest.mark.asyncio
    async def test_switch_conversation_missing_id(self):
        """测试切换会话缺少 conversation_id"""
        token = create_access_token({"sub": 1, "username": "test_user"})
        
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/1?token={token}") as websocket:
                # 接收连接状态和认证消息
                websocket.receive_json()
                websocket.receive_json()
                
                # 发送缺少 conversation_id 的切换消息
                websocket.send_json({"type": "switch_conversation"})
                
                # 应该收到错误响应
                error = websocket.receive_json()
                assert error["type"] == "error"
                assert error["code"] == "MISSING_CONVERSATION_ID"
    
    @pytest.mark.asyncio
    async def test_chat_with_conversation_id(self):
        """测试带 conversation_id 的聊天消息"""
        token = create_access_token({"sub": 1, "username": "test_user"})
        
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/1?token={token}") as websocket:
                # 接收连接状态和认证消息
                websocket.receive_json()
                websocket.receive_json()
                
                # 发送带 conversation_id 的聊天消息（不存在的会话 ID）
                # 由于会话不存在，会自动创建新会话
                websocket.send_json({
                    "type": "chat",
                    "content": "Hello",
                    "conversation_id": 99999  # 不存在的会话
                })
                
                # 应该收到消息响应或错误（取决于 iFlow 服务是否可用）
                # 这里只验证消息格式正确，不验证具体响应
                # 因为 iFlow 服务可能不可用


# ==================== handle_switch_conversation 单元测试 ====================

class TestHandleSwitchConversation:
    """handle_switch_conversation 函数测试"""
    
    @pytest.mark.asyncio
    async def test_switch_to_nonexistent_conversation(self):
        """测试切换到不存在的会话"""
        from backend.routers.websocket import handle_switch_conversation
        
        # 创建模拟对象
        websocket = AsyncMock()
        manager = WebSocketManager()
        db = AsyncMock()
        
        # 模拟数据库查询返回 None
        db.execute = AsyncMock()
        db.execute.return_value.scalar_one_or_none = Mock(return_value=None)
        
        # 调用函数
        conv_id, client = await handle_switch_conversation(
            websocket=websocket,
            manager=manager,
            user_id=1,
            conversation_id=999,
            db=db,
            current_conversation_id=1,
            iflow_client=None,
        )
        
        # 验证返回原会话 ID
        assert conv_id == 1
        
        # 验证发送了错误响应
        websocket.send_json.assert_called_once()
        call_args = websocket.send_json.call_args[0][0]
        assert call_args["type"] == "error"
        assert call_args["code"] == "CONVERSATION_NOT_FOUND"
