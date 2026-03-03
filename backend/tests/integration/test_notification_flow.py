"""
iFlow 对话网页应用 - 通知推送流程集成测试

测试完整的通知推送流程：
- 通知创建和存储
- 通知列表查询
- 通知已读标记
- 在线用户 WebSocket 推送
- 离线用户通知存储
"""
import pytest
import asyncio
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocket

from backend.database import get_db, Base
from backend.models.user import User
from backend.services.auth import create_access_token, hash_password
from backend.services.notification_store import NotificationStore
from backend.services.websocket_manager import (
    WebSocketManager,
    ConnectionStatus,
    ConnectionInfo,
    get_websocket_manager,
)
from backend.services.task_executor import TaskExecutor
from backend.routers import notifications


# ==================== 创建测试应用 ====================

def create_test_app():
    """创建测试用 FastAPI 应用"""
    test_app = FastAPI(
        title="iFlow Notification API (Test)",
        description="测试用应用",
        version="1.0.0",
    )
    
    # CORS 配置
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    test_app.include_router(
        notifications.router, 
        prefix="/api/notifications", 
        tags=["notifications"]
    )
    
    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    return test_app


# ==================== Fixtures ====================

@pytest.fixture(scope="function")
async def db_session():
    """创建测试数据库会话（使用内存数据库）"""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    
    # 创建表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建会话
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with test_session_maker() as session:
        yield session
    
    # 清理
    await test_engine.dispose()


@pytest.fixture(scope="function")
def temp_notifications_dir():
    """创建临时通知存储目录"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture(scope="function")
async def client(db_session, temp_notifications_dir):
    """创建测试客户端"""
    test_app = create_test_app()
    
    async def override_get_db():
        yield db_session
    
    test_app.dependency_overrides[get_db] = override_get_db
    
    # 创建临时通知存储
    notification_store = NotificationStore(notifications_dir=temp_notifications_dir)
    
    with patch('backend.routers.notifications.get_notification_store', return_value=notification_store):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    
    test_app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """创建测试用户"""
    user = User(
        username="notifuser",
        email="notif@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user: User):
    """生成认证 Token"""
    return create_access_token({"sub": test_user.id, "username": test_user.username})


@pytest.fixture
def auth_headers(auth_token: str):
    """生成认证请求头"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def notification_store(temp_notifications_dir):
    """创建通知存储实例"""
    return NotificationStore(notifications_dir=temp_notifications_dir)


@pytest.fixture
def websocket_manager():
    """创建新的 WebSocket 管理器实例"""
    return WebSocketManager()


# ==================== 通知创建和存储测试 ====================

@pytest.mark.asyncio
class TestNotificationCreationAndStorage:
    """通知创建和存储集成测试"""
    
    async def test_create_notification_success(
        self, 
        notification_store: NotificationStore
    ):
        """测试成功创建通知"""
        notification = notification_store.add_notification(
            user_id=1,
            task_id="task_001",
            content="定时任务执行成功"
        )
        
        assert notification is not None
        assert notification["id"].startswith("notif_")
        assert notification["task_id"] == "task_001"
        assert notification["content"] == "定时任务执行成功"
        assert notification["read"] is False
        assert "created_at" in notification
    
    async def test_notification_stored_in_file(
        self, 
        notification_store: NotificationStore,
        temp_notifications_dir
    ):
        """测试通知存储到文件"""
        notification_store.add_notification(
            user_id=1,
            task_id="task_001",
            content="测试通知"
        )
        
        # 验证文件已创建
        file_path = os.path.join(temp_notifications_dir, "1.json")
        assert os.path.exists(file_path)
        
        # 验证文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data["user_id"] == 1
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["content"] == "测试通知"
    
    async def test_multiple_notifications_order(
        self, 
        notification_store: NotificationStore
    ):
        """测试多个通知按时间倒序排列"""
        notification_store.add_notification(
            user_id=1,
            task_id="task_001",
            content="第一条通知"
        )
        
        notification_store.add_notification(
            user_id=1,
            task_id="task_002",
            content="第二条通知"
        )
        
        notification_store.add_notification(
            user_id=1,
            task_id="task_003",
            content="第三条通知"
        )
        
        result = notification_store.get_notifications(user_id=1)
        notifications = result["notifications"]
        
        assert len(notifications) == 3
        # 最新通知在最前面
        assert notifications[0]["content"] == "第三条通知"
        assert notifications[1]["content"] == "第二条通知"
        assert notifications[2]["content"] == "第一条通知"
    
    async def test_notification_limit(
        self, 
        notification_store: NotificationStore
    ):
        """测试通知数量限制（最多100条）"""
        # 创建 105 条通知
        for i in range(105):
            notification_store.add_notification(
                user_id=1,
                task_id=f"task_{i:03d}",
                content=f"通知_{i:03d}"
            )
        
        result = notification_store.get_notifications(user_id=1)
        
        # 应该只有 100 条
        assert result["total"] == 100
        # 最新的通知保留（104, 103, ..., 5）
        assert result["notifications"][0]["content"] == "通知_104"
    
    async def test_notification_for_different_users(
        self, 
        notification_store: NotificationStore
    ):
        """测试不同用户的通知隔离"""
        notification_store.add_notification(
            user_id=1,
            task_id="task_001",
            content="用户1的通知"
        )
        
        notification_store.add_notification(
            user_id=2,
            task_id="task_002",
            content="用户2的通知"
        )
        
        # 验证用户隔离
        result1 = notification_store.get_notifications(user_id=1)
        result2 = notification_store.get_notifications(user_id=2)
        
        assert result1["total"] == 1
        assert result1["notifications"][0]["content"] == "用户1的通知"
        
        assert result2["total"] == 1
        assert result2["notifications"][0]["content"] == "用户2的通知"
    
    async def test_notification_with_long_content(
        self, 
        notification_store: NotificationStore
    ):
        """测试长内容通知"""
        long_content = "这是一条很长的通知内容。" * 100
        
        notification = notification_store.add_notification(
            user_id=1,
            task_id="task_001",
            content=long_content
        )
        
        assert notification["content"] == long_content
        
        # 验证可以正确读取
        result = notification_store.get_notifications(user_id=1)
        assert result["notifications"][0]["content"] == long_content


# ==================== 通知列表查询测试 ====================

@pytest.mark.asyncio
class TestNotificationListQuery:
    """通知列表查询集成测试"""
    
    async def test_get_empty_notification_list(
        self, 
        client, 
        test_user, 
        auth_headers
    ):
        """测试获取空通知列表"""
        response = await client.get("/api/notifications", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["notifications"] == []
        assert data["unread_count"] == 0
        assert data["total"] == 0
    
    async def test_get_notification_list(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore
    ):
        """测试获取通知列表"""
        # 添加一些通知
        notification_store.add_notification(
            user_id=test_user.id,
            task_id="task_001",
            content="通知1"
        )
        notification_store.add_notification(
            user_id=test_user.id,
            task_id="task_002",
            content="通知2"
        )
        
        response = await client.get("/api/notifications", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["notifications"]) == 2
        assert data["total"] == 2
    
    async def test_get_unread_only_notifications(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore
    ):
        """测试只获取未读通知"""
        # 添加通知（通知按时间倒序，最新的在最前面）
        notification_store.add_notification(
            user_id=test_user.id,
            task_id="task_001",
            content="第一条通知（未读）"
        )
        notification_store.add_notification(
            user_id=test_user.id,
            task_id="task_002",
            content="第二条通知（将标记为已读）"
        )
        
        # 获取通知列表，第一条是最新的（第二条通知）
        notifications = notification_store.get_notifications(test_user.id)
        # 标记第一条（最新的）为已读
        notification_store.mark_as_read(
            test_user.id, 
            notifications["notifications"][0]["id"]  # 第二条通知
        )
        
        # 只获取未读
        response = await client.get(
            "/api/notifications?unread_only=true", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["content"] == "第一条通知（未读）"
    
    async def test_notification_pagination(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore
    ):
        """测试通知分页"""
        # 添加 10 条通知
        for i in range(10):
            notification_store.add_notification(
                user_id=test_user.id,
                task_id=f"task_{i:03d}",
                content=f"通知_{i:03d}"
            )
        
        # 获取第一页（5条）
        response = await client.get(
            "/api/notifications?limit=5&offset=0", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 5
        assert data["total"] == 10
        
        # 获取第二页
        response2 = await client.get(
            "/api/notifications?limit=5&offset=5", 
            headers=auth_headers
        )
        data2 = response2.json()
        assert len(data2["notifications"]) == 5
    
    async def test_notification_unread_count(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore
    ):
        """测试未读数量统计"""
        # 添加 5 条通知
        for i in range(5):
            notification_store.add_notification(
                user_id=test_user.id,
                task_id=f"task_{i:03d}",
                content=f"通知_{i:03d}"
            )
        
        # 标记 2 条为已读
        notifications = notification_store.get_notifications(test_user.id)
        notification_store.mark_as_read(
            test_user.id, 
            notifications["notifications"][0]["id"]
        )
        notification_store.mark_as_read(
            test_user.id, 
            notifications["notifications"][1]["id"]
        )
        
        response = await client.get("/api/notifications", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 3
        assert data["total"] == 5
    
    async def test_notification_list_unauthorized(self, client):
        """测试未授权获取通知列表"""
        response = await client.get("/api/notifications")
        assert response.status_code == 401
    
    async def test_notification_user_isolation(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore,
        db_session: AsyncSession
    ):
        """测试通知用户隔离"""
        # 创建另一个用户
        other_user = User(
            username="otheruser",
            email="other@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        # 为当前用户添加通知
        notification_store.add_notification(
            user_id=test_user.id,
            task_id="task_001",
            content="当前用户的通知"
        )
        
        # 为其他用户添加通知
        notification_store.add_notification(
            user_id=other_user.id,
            task_id="task_002",
            content="其他用户的通知"
        )
        
        # 当前用户应该只能看到自己的通知
        response = await client.get("/api/notifications", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["content"] == "当前用户的通知"


# ==================== 通知已读标记测试 ====================

@pytest.mark.asyncio
class TestNotificationMarkRead:
    """通知已读标记集成测试"""
    
    async def test_mark_single_notification_as_read(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore
    ):
        """测试标记单条通知为已读"""
        notification = notification_store.add_notification(
            user_id=test_user.id,
            task_id="task_001",
            content="测试通知"
        )
        
        response = await client.put(
            f"/api/notifications/{notification['id']}/read",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "已标记为已读"
        
        # 验证通知已标记为已读
        notifications = notification_store.get_notifications(test_user.id)
        assert notifications["notifications"][0]["read"] is True
    
    async def test_mark_all_notifications_as_read(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore
    ):
        """测试标记所有通知为已读"""
        # 添加 5 条通知
        for i in range(5):
            notification_store.add_notification(
                user_id=test_user.id,
                task_id=f"task_{i:03d}",
                content=f"通知_{i:03d}"
            )
        
        response = await client.put(
            "/api/notifications/read-all",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 5
        
        # 验证所有通知已标记为已读
        notifications = notification_store.get_notifications(test_user.id)
        assert all(n["read"] for n in notifications["notifications"])
    
    async def test_mark_nonexistent_notification(
        self, 
        client, 
        test_user, 
        auth_headers
    ):
        """测试标记不存在的通知"""
        response = await client.put(
            "/api/notifications/nonexistent_notif/read",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    async def test_mark_already_read_notification(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore
    ):
        """测试标记已读的通知"""
        notification = notification_store.add_notification(
            user_id=test_user.id,
            task_id="task_001",
            content="测试通知"
        )
        
        # 第一次标记
        response1 = await client.put(
            f"/api/notifications/{notification['id']}/read",
            headers=auth_headers
        )
        assert response1.status_code == 200
        
        # 第二次标记（应该仍然成功）
        response2 = await client.put(
            f"/api/notifications/{notification['id']}/read",
            headers=auth_headers
        )
        assert response2.status_code == 200
    
    async def test_mark_read_unauthorized(self, client):
        """测试未授权标记已读"""
        response = await client.put("/api/notifications/notif_001/read")
        assert response.status_code == 401


# ==================== 在线用户 WebSocket 推送测试 ====================

@pytest.mark.asyncio
class TestOnlineUserWebSocketPush:
    """在线用户 WebSocket 推送集成测试"""
    
    async def test_push_to_online_user(
        self, 
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试推送通知给在线用户"""
        # Mock WebSocket
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.send_json = AsyncMock()
        
        # 注册连接
        conn_info = await websocket_manager.connect(mock_websocket, user_id=1)
        await websocket_manager.authenticate(conn_info.connection_id)
        
        # 创建执行器
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        # Mock iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "任务执行结果"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="测试任务"
            )
        
        assert result["success"] is True
        assert result["pushed"] is True
        
        # 验证 WebSocket 推送被调用
        mock_websocket.send_json.assert_called()
        
        # 验证推送消息格式
        call_args = mock_websocket.send_json.call_args
        message = call_args[0][0]
        assert message["type"] == "notification"
        assert "notification" in message
        assert message["notification"]["task_id"] == "task_001"
    
    async def test_push_to_multiple_connections(
        self, 
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试推送到用户的多个连接（多标签页）"""
        # Mock 多个 WebSocket 连接
        mock_ws1 = MagicMock(spec=WebSocket)
        mock_ws1.send_json = AsyncMock()
        
        mock_ws2 = MagicMock(spec=WebSocket)
        mock_ws2.send_json = AsyncMock()
        
        # 注册两个连接
        conn1 = await websocket_manager.connect(mock_ws1, user_id=1)
        await websocket_manager.authenticate(conn1.connection_id)
        
        conn2 = await websocket_manager.connect(mock_ws2, user_id=1)
        await websocket_manager.authenticate(conn2.connection_id)
        
        # 创建执行器
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        # Mock iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "结果"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="测试"
            )
        
        assert result["success"] is True
        assert result["pushed"] is True
        
        # 验证两个连接都收到推送
        mock_ws1.send_json.assert_called()
        mock_ws2.send_json.assert_called()
    
    async def test_push_failure_does_not_affect_storage(
        self, 
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试推送失败不影响通知存储"""
        # Mock WebSocket 发送失败
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.send_json = AsyncMock(side_effect=Exception("连接已断开"))
        
        # 注册连接
        conn_info = await websocket_manager.connect(mock_websocket, user_id=1)
        await websocket_manager.authenticate(conn_info.connection_id)
        
        # 创建执行器
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        # Mock iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "结果"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="测试"
            )
        
        # 推送失败，但任务执行成功
        assert result["success"] is True
        assert result["pushed"] is False
        
        # 通知仍然应该被存储
        assert result["notification"] is not None
        
        # 验证通知已保存
        notifications = notification_store.get_notifications(user_id=1)
        assert notifications["total"] == 1
    
    async def test_notification_message_format(
        self, 
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试通知消息格式"""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.send_json = AsyncMock()
        
        conn_info = await websocket_manager.connect(mock_websocket, user_id=1)
        await websocket_manager.authenticate(conn_info.connection_id)
        
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "执行结果内容"
            
            await executor.execute_task(
                user_id=1,
                task_id="task_test",
                content="查看股票"
            )
        
        # 验证推送消息格式
        call_args = mock_websocket.send_json.call_args
        message = call_args[0][0]
        
        assert "type" in message
        assert message["type"] == "notification"
        assert "notification" in message
        
        notification = message["notification"]
        assert "id" in notification
        assert notification["task_id"] == "task_test"
        assert "content" in notification
        assert "查看股票" in notification["content"]
        assert notification["read"] is False
        assert "created_at" in notification


# ==================== 离线用户通知存储测试 ====================

@pytest.mark.asyncio
class TestOfflineUserNotificationStorage:
    """离线用户通知存储集成测试"""
    
    async def test_no_push_for_offline_user(
        self, 
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试离线用户不收到推送"""
        # 不注册任何连接，用户离线
        
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        # Mock iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "执行结果"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="测试任务"
            )
        
        assert result["success"] is True
        assert result["pushed"] is False
        
        # 通知应该被存储
        assert result["notification"] is not None
        
        # 验证通知已保存到文件
        notifications = notification_store.get_notifications(user_id=1)
        assert notifications["total"] == 1
    
    async def test_offline_user_can_retrieve_later(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试离线用户稍后可以查看通知"""
        # 用户离线时执行任务
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "任务结果"
            
            await executor.execute_task(
                user_id=test_user.id,
                task_id="task_001",
                content="查看天气"
            )
        
        # 用户上线后查询通知
        response = await client.get("/api/notifications", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 1
        assert "查看天气" in data["notifications"][0]["content"]
    
    async def test_multiple_tasks_while_offline(
        self, 
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试离线期间多个任务执行"""
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        # 执行多个任务
        for i in range(3):
            with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
                mock_iflow.return_value = f"结果_{i}"
                
                await executor.execute_task(
                    user_id=1,
                    task_id=f"task_{i:03d}",
                    content=f"任务_{i}"
                )
        
        # 验证所有通知已存储
        notifications = notification_store.get_notifications(user_id=1)
        assert notifications["total"] == 3
    
    async def test_offline_then_online_sequence(
        self, 
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试离线后上线的通知处理"""
        # 用户离线时执行任务
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "离线任务结果"
            
            offline_result = await executor.execute_task(
                user_id=1,
                task_id="task_offline",
                content="离线任务"
            )
        
        assert offline_result["pushed"] is False
        
        # 用户上线
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.send_json = AsyncMock()
        
        conn_info = await websocket_manager.connect(mock_websocket, user_id=1)
        await websocket_manager.authenticate(conn_info.connection_id)
        
        # 用户在线时执行另一个任务
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "在线任务结果"
            
            online_result = await executor.execute_task(
                user_id=1,
                task_id="task_online",
                content="在线任务"
            )
        
        assert online_result["pushed"] is True
        
        # 验证两条通知都已存储
        notifications = notification_store.get_notifications(user_id=1)
        assert notifications["total"] == 2


# ==================== 完整通知流程集成测试 ====================

@pytest.mark.asyncio
class TestFullNotificationFlow:
    """完整通知流程集成测试"""
    
    async def test_full_notification_lifecycle(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试完整通知生命周期：创建 -> 查询 -> 已读 -> 删除"""
        # 1. 创建通知（通过任务执行）
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "执行结果"
            
            await executor.execute_task(
                user_id=test_user.id,
                task_id="task_001",
                content="测试任务"
            )
        
        # 2. 查询通知
        response = await client.get("/api/notifications", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 1
        assert data["unread_count"] == 1
        
        notification_id = data["notifications"][0]["id"]
        
        # 3. 标记已读
        response = await client.put(
            f"/api/notifications/{notification_id}/read",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # 4. 验证已读状态
        response = await client.get("/api/notifications", headers=auth_headers)
        assert response.json()["unread_count"] == 0
        
        # 5. 删除通知
        response = await client.delete(
            f"/api/notifications/{notification_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # 6. 验证已删除
        response = await client.get("/api/notifications", headers=auth_headers)
        assert response.json()["total"] == 0
    
    async def test_multiple_users_notification_flow(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager,
        db_session: AsyncSession
    ):
        """测试多用户通知流程"""
        # 创建另一个用户
        other_user = User(
            username="otheruser",
            email="other@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        # 为两个用户执行任务
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "结果"
            
            await executor.execute_task(
                user_id=test_user.id,
                task_id="task_user1",
                content="用户1任务"
            )
            
            await executor.execute_task(
                user_id=other_user.id,
                task_id="task_user2",
                content="用户2任务"
            )
        
        # 验证用户隔离
        response = await client.get("/api/notifications", headers=auth_headers)
        data = response.json()
        
        assert len(data["notifications"]) == 1
        assert "用户1任务" in data["notifications"][0]["content"]
    
    async def test_concurrent_task_execution(
        self, 
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试并发任务执行"""
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        # 并发执行多个任务
        async def execute_task(task_id: str, content: str):
            with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
                mock_iflow.return_value = f"结果_{task_id}"
                return await executor.execute_task(
                    user_id=1,
                    task_id=task_id,
                    content=content
                )
        
        results = await asyncio.gather(
            execute_task("task_001", "任务1"),
            execute_task("task_002", "任务2"),
            execute_task("task_003", "任务3"),
        )
        
        # 所有任务应该成功
        assert all(r["success"] for r in results)
        
        # 所有通知应该被存储
        notifications = notification_store.get_notifications(user_id=1)
        assert notifications["total"] == 3
    
    async def test_error_notification_still_saved(
        self, 
        notification_store: NotificationStore,
        websocket_manager: WebSocketManager
    ):
        """测试执行失败时通知仍然被保存"""
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=websocket_manager,
        )
        
        # Mock iFlow 抛出异常
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.side_effect = Exception("iFlow 连接失败")
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_error",
                content="会失败的任务"
            )
        
        # 执行失败
        assert result["success"] is False
        assert "iFlow 连接失败" in result["error"]
        
        # 失败通知应该被保存
        assert result["notification"] is not None
        assert "执行失败" in result["notification"]["content"]
        
        # 验证存储
        notifications = notification_store.get_notifications(user_id=1)
        assert notifications["total"] == 1


# ==================== 通知删除测试 ====================

@pytest.mark.asyncio
class TestNotificationDelete:
    """通知删除集成测试"""
    
    async def test_delete_single_notification(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore
    ):
        """测试删除单条通知"""
        notification = notification_store.add_notification(
            user_id=test_user.id,
            task_id="task_001",
            content="要删除的通知"
        )
        
        response = await client.delete(
            f"/api/notifications/{notification['id']}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "已删除" in data["message"]
        
        # 验证已删除
        notifications = notification_store.get_notifications(test_user.id)
        assert notifications["total"] == 0
    
    async def test_delete_nonexistent_notification(
        self, 
        client, 
        test_user, 
        auth_headers
    ):
        """测试删除不存在的通知"""
        response = await client.delete(
            "/api/notifications/nonexistent_notif",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    async def test_clear_all_notifications(
        self, 
        client, 
        test_user, 
        auth_headers,
        notification_store: NotificationStore
    ):
        """测试清除所有通知"""
        # 添加多条通知
        for i in range(5):
            notification_store.add_notification(
                user_id=test_user.id,
                task_id=f"task_{i:03d}",
                content=f"通知_{i}"
            )
        
        response = await client.delete(
            "/api/notifications",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "5 条" in data["message"]
        
        # 验证已清空
        notifications = notification_store.get_notifications(test_user.id)
        assert notifications["total"] == 0
    
    async def test_delete_notification_unauthorized(self, client):
        """测试未授权删除通知"""
        response = await client.delete("/api/notifications/notif_001")
        assert response.status_code == 401
