"""
边界情况处理与错误恢复测试

测试内容：
1. WebSocket 网络断开重连
2. 任务执行失败场景
3. 大量消息分页加载
4. iFlow 服务不可用场景
5. Token 过期刷新
"""
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient

from backend.main import app
from backend.services.auth import (
    create_access_token,
    decode_access_token,
    is_token_expired,
    should_refresh_token,
    refresh_access_token,
    get_token_info,
    get_current_user,
)
from backend.services.iflow_client import IFlowClientService, MessageType
from backend.services.task_executor import TaskExecutor
from backend.services.notification_store import NotificationStore
from backend.services.websocket_manager import WebSocketManager
from backend.models.user import User


# ==================== Fixtures ====================

@pytest.fixture
def mock_db():
    """Mock 数据库会话"""
    db = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    """Mock 用户"""
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        created_at=datetime.now(timezone.utc),
    )
    return user


@pytest.fixture
def mock_notification_store():
    """Mock 通知存储"""
    store = MagicMock(spec=NotificationStore)
    store.add_notification = MagicMock(return_value={
        "id": "notif_1",
        "task_id": "task_1",
        "content": "Test notification",
        "read": False,
        "created_at": datetime.now().isoformat(),
    })
    return store


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket 管理器"""
    manager = MagicMock(spec=WebSocketManager)
    manager.is_user_online = MagicMock(return_value=False)
    manager.send_to_user = AsyncMock(return_value=0)
    return manager


# ==================== Token 过期刷新测试 ====================

class TestTokenExpirationAndRefresh:
    """Token 过期和刷新测试"""
    
    def test_create_and_decode_token(self):
        """测试创建和解码 Token"""
        token = create_access_token({"sub": 1, "username": "testuser"})
        
        assert token is not None
        assert isinstance(token, str)
        
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == 1
        assert payload["username"] == "testuser"
    
    def test_token_not_expired(self):
        """测试 Token 未过期"""
        token = create_access_token({"sub": 1, "username": "testuser"})
        
        assert is_token_expired(token) is False
    
    def test_token_expired(self):
        """测试 Token 已过期"""
        # 创建一个已过期的 Token
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": 1,
            "username": "testuser",
            "exp": expired_time.timestamp(),
            "iat": (expired_time - timedelta(hours=1)).timestamp(),
        }
        
        from jose import jwt
        from backend.config import settings
        
        expired_token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        assert is_token_expired(expired_token) is True
    
    def test_should_refresh_token_false(self):
        """测试 Token 不需要刷新"""
        token = create_access_token({"sub": 1, "username": "testuser"})
        
        # 新创建的 Token 不应该需要刷新
        assert should_refresh_token(token) is False
    
    def test_should_refresh_token_true(self):
        """测试 Token 需要刷新"""
        # 创建一个即将过期的 Token（有效期只剩 1 分钟）
        from jose import jwt
        from backend.config import settings
        
        exp_time = datetime.now(timezone.utc) + timedelta(minutes=1)
        payload = {
            "sub": 1,
            "username": "testuser",
            "exp": exp_time.timestamp(),
            "iat": datetime.now(timezone.utc).timestamp(),
        }
        
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        assert should_refresh_token(token) is True
    
    def test_refresh_token(self):
        """测试刷新 Token"""
        old_token = create_access_token({"sub": 1, "username": "testuser"})
        
        # 等待一小段时间确保新 Token 不同
        import time
        time.sleep(1)
        
        new_token = refresh_access_token(old_token)
        
        assert new_token is not None
        assert new_token != old_token
        
        # 验证新 Token 的内容
        new_payload = decode_access_token(new_token)
        assert new_payload["sub"] == 1
        assert new_payload["username"] == "testuser"
    
    def test_refresh_expired_token_fails(self):
        """测试刷新已过期的 Token 失败"""
        from jose import jwt
        from backend.config import settings
        
        # 创建一个已过期的 Token
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": 1,
            "username": "testuser",
            "exp": expired_time.timestamp(),
            "iat": (expired_time - timedelta(hours=1)).timestamp(),
        }
        
        expired_token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        # 刷新已过期的 Token 应该返回 None
        new_token = refresh_access_token(expired_token)
        assert new_token is None
    
    def test_get_token_info(self):
        """测试获取 Token 信息"""
        token = create_access_token({"sub": 1, "username": "testuser"})
        
        info = get_token_info(token)
        
        assert info["valid"] is True
        assert info["expired"] is False
        assert info["should_refresh"] is False
        assert info["user_id"] == 1
        assert info["username"] == "testuser"
        assert info["remaining_seconds"] > 0
    
    def test_get_token_info_expired(self):
        """测试获取过期 Token 信息"""
        from jose import jwt
        from backend.config import settings
        
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": 1,
            "username": "testuser",
            "exp": expired_time.timestamp(),
        }
        
        expired_token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        info = get_token_info(expired_token)
        
        assert info["valid"] is False
        assert info["expired"] is True


# ==================== iFlow 服务不可用测试 ====================

class TestIFlowServiceUnavailable:
    """iFlow 服务不可用测试"""
    
    @pytest.mark.asyncio
    async def test_connection_failure_with_retries(self):
        """测试连接失败时的重试机制"""
        client = IFlowClientService(
            url="ws://invalid-host:8090/acp",
            max_reconnect_attempts=2,
            reconnect_base_delay=0.1,  # 快速测试
        )
        
        # 应该在重试后抛出异常
        with pytest.raises(ConnectionError) as exc_info:
            await client.connect()
        
        assert "Failed to connect" in str(exc_info.value)
        assert client.is_connected is False
    
    @pytest.mark.asyncio
    async def test_service_unavailable_detection(self):
        """测试服务不可用检测"""
        client = IFlowClientService()
        
        # 初始状态应该可用
        assert client.is_service_available is True
        
        # 模拟连续失败
        client._record_failure("Error 1")
        client._record_failure("Error 2")
        client._record_failure("Error 3")
        
        # 达到阈值后应该标记为不可用
        assert client.is_service_available is False
        assert client._consecutive_failures == 3
    
    @pytest.mark.asyncio
    async def test_service_recovery(self):
        """测试服务恢复"""
        client = IFlowClientService()
        
        # 先标记为不可用
        client._record_failure("Error 1")
        client._record_failure("Error 2")
        client._record_failure("Error 3")
        assert client.is_service_available is False
        
        # 记录成功后应该恢复
        client._record_success()
        assert client.is_service_available is True
        assert client._consecutive_failures == 0
    
    @pytest.mark.asyncio
    async def test_get_connection_status(self):
        """测试获取连接状态"""
        client = IFlowClientService()
        
        status = client.get_connection_status()
        
        assert "is_connected" in status
        assert "is_service_available" in status
        assert "url" in status
        assert "consecutive_failures" in status


# ==================== 任务执行失败测试 ====================

class TestTaskExecutionFailure:
    """任务执行失败测试"""
    
    @pytest.mark.asyncio
    async def test_task_retry_on_failure(self, mock_notification_store, mock_websocket_manager):
        """测试任务执行失败时的重试机制"""
        executor = TaskExecutor(
            notification_store=mock_notification_store,
            websocket_manager=mock_websocket_manager,
            max_retries=2,
            retry_delay=0.1,  # 快速测试
        )
        
        # Mock _call_iflow 使其失败
        call_count = 0
        
        async def mock_call_iflow(message):
            nonlocal call_count
            call_count += 1
            raise Exception("iFlow service error")
        
        executor._call_iflow = mock_call_iflow
        
        # 执行任务
        result = await executor.execute_task(
            user_id=1,
            task_id="task_1",
            content="Test task",
        )
        
        # 应该重试 max_retries + 1 次
        assert call_count == 3  # 初始 + 2 次重试
        assert result["success"] is False
        assert result["retries"] == 2
        assert "iFlow service error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_task_success_after_retry(self, mock_notification_store, mock_websocket_manager):
        """测试任务在重试后成功"""
        executor = TaskExecutor(
            notification_store=mock_notification_store,
            websocket_manager=mock_websocket_manager,
            max_retries=2,
            retry_delay=0.1,
        )
        
        # Mock _call_iflow 使其第一次失败，第二次成功
        call_count = 0
        
        async def mock_call_iflow(message):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary error")
            return "Success response"
        
        executor._call_iflow = mock_call_iflow
        
        result = await executor.execute_task(
            user_id=1,
            task_id="task_1",
            content="Test task",
        )
        
        assert call_count == 2
        assert result["success"] is True
        assert result["retries"] == 1
        assert result["response"] == "Success response"
    
    @pytest.mark.asyncio
    async def test_execution_history(self, mock_notification_store, mock_websocket_manager):
        """测试执行历史记录"""
        executor = TaskExecutor(
            notification_store=mock_notification_store,
            websocket_manager=mock_websocket_manager,
        )
        
        # Mock _call_iflow
        executor._call_iflow = AsyncMock(return_value="Success")
        
        # 执行多次任务
        for i in range(15):
            await executor.execute_task(
                user_id=1,
                task_id="task_1",
                content=f"Task {i}",
            )
        
        # 应该只保留最近 10 次记录
        history = executor.get_execution_history("task_1")
        assert len(history) == 10
    
    @pytest.mark.asyncio
    async def test_failure_notification_saved(self, mock_notification_store, mock_websocket_manager):
        """测试失败时仍然保存通知"""
        executor = TaskExecutor(
            notification_store=mock_notification_store,
            websocket_manager=mock_websocket_manager,
            max_retries=0,
        )
        
        # Mock _call_iflow 使其失败
        executor._call_iflow = AsyncMock(side_effect=Exception("iFlow error"))
        
        result = await executor.execute_task(
            user_id=1,
            task_id="task_1",
            content="Test task",
        )
        
        # 即使失败，也应该保存通知
        assert result["success"] is False
        assert result["notification"] is not None
        mock_notification_store.add_notification.assert_called()


# ==================== 大量消息分页测试 ====================

class TestMessagePagination:
    """大量消息分页测试"""
    
    @pytest.mark.asyncio
    async def test_pagination_with_many_messages(self, mock_db, mock_user):
        """测试大量消息的分页"""
        from backend.routers.chat import get_chat_history, ChatHistoryResponse
        from backend.models.user import ChatHistory
        from sqlalchemy import func
        
        # Mock 大量消息
        mock_messages = []
        for i in range(100):
            msg = ChatHistory(
                id=i + 1,
                user_id=1,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i + 1}",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=i),
            )
            mock_messages.append(msg)
        
        # Mock 数据库查询
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_messages[:21]  # 模拟 has_more
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Mock count 查询
        count_result = MagicMock()
        count_result.scalar.return_value = 100
        mock_db.execute = AsyncMock(side_effect=[count_result, mock_result])
        
        # 调用分页函数
        response = await get_chat_history(
            page=1,
            page_size=20,
            before_id=None,
            current_user=mock_user,
            db=mock_db,
        )
        
        assert response.total == 100
        assert response.has_more is True
        assert response.total_pages == 5
    
    @pytest.mark.asyncio
    async def test_cursor_pagination_before_id(self, mock_db, mock_user):
        """测试游标分页（向前翻页）"""
        from backend.routers.chat import get_chat_history
        from backend.models.user import ChatHistory
        
        # Mock 消息
        mock_messages = []
        for i in range(20):
            msg = ChatHistory(
                id=100 - i,  # ID 递减
                user_id=1,
                role="user",
                content=f"Message {100 - i}",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=i),
            )
            mock_messages.append(msg)
        
        # Mock count 查询
        count_result = MagicMock()
        count_result.scalar.return_value = 100
        
        # Mock 消息查询
        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = mock_messages
        
        mock_db.execute = AsyncMock(side_effect=[count_result, msg_result])
        
        response = await get_chat_history(
            page=1,
            page_size=20,
            before_id=100,
            current_user=mock_user,
            db=mock_db,
        )
        
        # 使用游标分页时，应该获取 ID < before_id 的消息
        assert response.total == 100
    
    @pytest.mark.asyncio
    async def test_cursor_pagination_after_id(self, mock_db, mock_user):
        """测试游标分页（向后翻页）"""
        from backend.routers.chat import get_chat_history
        from backend.models.user import ChatHistory
        
        # Mock 消息
        mock_messages = []
        for i in range(20):
            msg = ChatHistory(
                id=200 + i,  # ID 递增
                user_id=1,
                role="user",
                content=f"Message {200 + i}",
                created_at=datetime.now(timezone.utc) + timedelta(minutes=i),
            )
            mock_messages.append(msg)
        
        # Mock count 查询
        count_result = MagicMock()
        count_result.scalar.return_value = 100
        
        # Mock 消息查询
        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = mock_messages
        
        mock_db.execute = AsyncMock(side_effect=[count_result, msg_result])
        
        response = await get_chat_history(
            page=1,
            page_size=20,
            after_id=199,
            current_user=mock_user,
            db=mock_db,
        )
        
        # 使用游标分页时，应该获取 ID > after_id 的消息
        assert response.total == 100


# ==================== WebSocket 重连测试 ====================

class TestWebSocketReconnect:
    """WebSocket 重连测试"""
    
    @pytest.mark.asyncio
    async def test_reconnect_success(self):
        """测试重连成功"""
        client = IFlowClientService()
        
        # Mock connect 和 disconnect
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        
        result = await client.reconnect()
        
        assert result is True
        client.disconnect.assert_called_once()
        client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reconnect_failure(self):
        """测试重连失败"""
        client = IFlowClientService()
        
        # Mock disconnect 成功，connect 失败
        client.disconnect = AsyncMock()
        client.connect = AsyncMock(side_effect=Exception("Connection failed"))
        
        result = await client.reconnect()
        
        assert result is False


# ==================== 错误处理服务测试 ====================

class TestErrorHandlerService:
    """错误处理服务测试"""
    
    def test_reconnect_manager_delay_calculation(self):
        """测试重连管理器延迟计算"""
        from backend.services.error_handler import ReconnectManager
        
        manager = ReconnectManager(
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=30.0,
        )
        
        # 验证指数退避
        assert manager.calculate_delay(0) == 1.0
        assert manager.calculate_delay(1) == 2.0
        assert manager.calculate_delay(2) == 4.0
        assert manager.calculate_delay(3) == 8.0
        
        # 验证最大延迟
        assert manager.calculate_delay(10) == 30.0
    
    @pytest.mark.asyncio
    async def test_reconnect_manager_execute_with_retry(self):
        """测试带重试的执行"""
        from backend.services.error_handler import ReconnectManager
        
        manager = ReconnectManager(max_retries=2, base_delay=0.1)
        
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return "success"
        
        result = await manager.execute_with_retry(failing_func)
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_reconnect_manager_max_retries_exceeded(self):
        """测试超过最大重试次数"""
        from backend.services.error_handler import ReconnectManager
        
        manager = ReconnectManager(max_retries=2, base_delay=0.1)
        
        async def always_fail():
            raise Exception("Always fails")
        
        with pytest.raises(Exception) as exc_info:
            await manager.execute_with_retry(always_fail)
        
        assert "Always fails" in str(exc_info.value)
    
    def test_iflow_service_monitor(self):
        """测试 iFlow 服务监控器"""
        from backend.services.error_handler import IFlowServiceMonitor
        
        monitor = IFlowServiceMonitor(
            unhealthy_threshold=3,
            recovery_threshold=2,
        )
        
        # 初始状态应该健康
        assert monitor.is_healthy is True
        
        # 记录失败
        monitor.record_failure("Error 1")
        monitor.record_failure("Error 2")
        assert monitor.is_healthy is True
        
        monitor.record_failure("Error 3")
        assert monitor.is_healthy is False
        
        # 记录成功恢复
        monitor.record_success()
        monitor.record_success()
        assert monitor.is_healthy is True
    
    def test_token_refresh_handler(self):
        """测试 Token 刷新处理器"""
        from backend.services.error_handler import TokenRefreshHandler
        
        handler = TokenRefreshHandler(refresh_threshold_minutes=5)
        
        # 创建即将过期的 payload
        exp_time = datetime.now(timezone.utc) + timedelta(minutes=2)
        payload = {"exp": exp_time.timestamp(), "sub": 1}
        
        # 应该需要刷新
        assert handler.should_refresh(payload) is True
        assert handler.is_expired(payload) is False
        
        # 创建已过期的 payload
        expired_payload = {
            "exp": (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp(),
            "sub": 1
        }
        
        assert handler.is_expired(expired_payload) is True


# ==================== 集成测试 ====================

class TestErrorHandlingIntegration:
    """错误处理集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_task_retry_flow(self, mock_notification_store, mock_websocket_manager):
        """测试完整的任务重试流程"""
        executor = TaskExecutor(
            notification_store=mock_notification_store,
            websocket_manager=mock_websocket_manager,
            max_retries=2,
            retry_delay=0.1,
        )
        
        # 模拟网络抖动场景：前两次失败，第三次成功
        call_count = 0
        
        async def unstable_iflow(message):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Network unstable")
            return "Success after retries"
        
        executor._call_iflow = unstable_iflow
        
        result = await executor.execute_task(
            user_id=1,
            task_id="unstable_task",
            content="Task with network issues",
        )
        
        assert result["success"] is True
        assert result["retries"] == 2
        assert result["response"] == "Success after retries"
        
        # 验证通知被保存
        assert result["notification"] is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_task_failures(self, mock_notification_store, mock_websocket_manager):
        """测试并发任务失败处理"""
        executor = TaskExecutor(
            notification_store=mock_notification_store,
            websocket_manager=mock_websocket_manager,
            max_retries=0,
        )
        
        # Mock 失败的 iFlow 调用
        executor._call_iflow = AsyncMock(side_effect=Exception("Service down"))
        
        # 并发执行多个任务
        tasks = [
            executor.execute_task(user_id=1, task_id=f"task_{i}", content=f"Task {i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # 所有任务都应该失败但保存了通知
        for result in results:
            assert result["success"] is False
            assert result["notification"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
