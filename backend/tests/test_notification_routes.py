"""
通知 API 路由测试
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from datetime import datetime

from backend.main import app
from backend.database import get_db, Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from backend.models.user import User
from backend.services.auth import create_access_token, hash_password
from backend.services.notification_store import NotificationStore


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
async def client(db_session):
    """创建测试客户端"""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session):
    """创建测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """生成认证头"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_store(tmp_path):
    """创建临时通知存储"""
    return NotificationStore(notifications_dir=str(tmp_path / "notifications"))


# ==================== 获取通知列表测试 ====================

@pytest.mark.asyncio
async def test_get_notifications_empty(client, test_user, mock_store):
    """测试获取空通知列表"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["notifications"] == []
        assert data["unread_count"] == 0
        assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_notifications_with_data(client, test_user, mock_store):
    """测试获取有数据的通知列表"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    # 添加测试通知
    mock_store.add_notification(user_id=test_user.id, task_id="task_001", content="通知1")
    mock_store.add_notification(user_id=test_user.id, task_id="task_002", content="通知2")
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["notifications"]) == 2
        assert data["total"] == 2
        assert data["unread_count"] == 2


@pytest.mark.asyncio
async def test_get_notifications_unread_only(client, test_user, mock_store):
    """测试只获取未读通知"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    # 添加测试通知
    notif1 = mock_store.add_notification(user_id=test_user.id, task_id="task_001", content="通知1")
    notif2 = mock_store.add_notification(user_id=test_user.id, task_id="task_002", content="通知2")
    
    # 标记第一个为已读
    mock_store.mark_as_read(user_id=test_user.id, notification_id=notif1["id"])
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.get(
            "/api/notifications?unread_only=true",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["id"] == notif2["id"]
        assert data["unread_count"] == 1


@pytest.mark.asyncio
async def test_get_notifications_pagination(client, test_user, mock_store):
    """测试通知分页"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    # 添加多个通知
    for i in range(10):
        mock_store.add_notification(user_id=test_user.id, task_id=f"task_{i:03d}", content=f"通知{i}")
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        # 第一页
        response = await client.get(
            "/api/notifications?limit=5&offset=0",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 5
        assert data["total"] == 10
        
        # 第二页
        response = await client.get(
            "/api/notifications?limit=5&offset=5",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 5


@pytest.mark.asyncio
async def test_get_notifications_newest_first(client, test_user, mock_store):
    """测试通知按时间倒序（最新在前）"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    notif1 = mock_store.add_notification(user_id=test_user.id, task_id="task_001", content="第一条通知")
    notif2 = mock_store.add_notification(user_id=test_user.id, task_id="task_002", content="第二条通知")
    notif3 = mock_store.add_notification(user_id=test_user.id, task_id="task_003", content="第三条通知")
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = response.json()
        
        # 最新的应该在前面
        assert data["notifications"][0]["id"] == notif3["id"]
        assert data["notifications"][1]["id"] == notif2["id"]
        assert data["notifications"][2]["id"] == notif1["id"]


@pytest.mark.asyncio
async def test_get_notifications_unauthorized(client):
    """测试未授权获取通知列表"""
    response = await client.get("/api/notifications")
    assert response.status_code == 401


# ==================== 标记已读测试 ====================

@pytest.mark.asyncio
async def test_mark_notification_as_read_success(client, test_user, mock_store):
    """测试成功标记已读"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    notif = mock_store.add_notification(user_id=test_user.id, task_id="task_001", content="测试通知")
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.put(
            f"/api/notifications/{notif['id']}/read",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "已标记为已读" in data["message"]
        
        # 验证已标记
        result = mock_store.get_notifications(user_id=test_user.id)
        assert result["unread_count"] == 0


@pytest.mark.asyncio
async def test_mark_notification_as_read_not_found(client, test_user, mock_store):
    """测试标记不存在通知"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.put(
            "/api/notifications/notif_notexist/read",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_mark_notification_already_read(client, test_user, mock_store):
    """测试标记已读的通知"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    notif = mock_store.add_notification(user_id=test_user.id, task_id="task_001", content="测试通知")
    
    # 先标记已读
    mock_store.mark_as_read(user_id=test_user.id, notification_id=notif["id"])
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        # 再次标记
        response = await client.put(
            f"/api/notifications/{notif['id']}/read",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True


# ==================== 标记全部已读测试 ====================

@pytest.mark.asyncio
async def test_mark_all_as_read_success(client, test_user, mock_store):
    """测试成功标记全部已读"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    # 添加多个通知
    for i in range(5):
        mock_store.add_notification(user_id=test_user.id, task_id=f"task_{i:03d}", content=f"通知{i}")
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.put(
            "/api/notifications/read-all",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 5
        
        # 验证全部已读
        result = mock_store.get_notifications(user_id=test_user.id)
        assert result["unread_count"] == 0


@pytest.mark.asyncio
async def test_mark_all_as_read_empty(client, test_user, mock_store):
    """测试空通知列表标记全部已读"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.put(
            "/api/notifications/read-all",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0


# ==================== 删除通知测试 ====================

@pytest.mark.asyncio
async def test_delete_notification_success(client, test_user, mock_store):
    """测试成功删除通知"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    notif = mock_store.add_notification(user_id=test_user.id, task_id="task_001", content="测试通知")
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.delete(
            f"/api/notifications/{notif['id']}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "已删除" in data["message"]
        
        # 验证已删除
        result = mock_store.get_notifications(user_id=test_user.id)
        assert result["total"] == 0


@pytest.mark.asyncio
async def test_delete_notification_not_found(client, test_user, mock_store):
    """测试删除不存在的通知"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.delete(
            "/api/notifications/notif_notexist",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404


# ==================== 清除所有通知测试 ====================

@pytest.mark.asyncio
async def test_clear_all_notifications_success(client, test_user, mock_store):
    """测试成功清除所有通知"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    # 添加多个通知
    for i in range(10):
        mock_store.add_notification(user_id=test_user.id, task_id=f"task_{i:03d}", content=f"通知{i}")
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.delete(
            "/api/notifications",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "10" in data["message"]
        
        # 验证已清除
        result = mock_store.get_notifications(user_id=test_user.id)
        assert result["total"] == 0


@pytest.mark.asyncio
async def test_clear_all_notifications_empty(client, test_user, mock_store):
    """测试清除空通知列表"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.delete(
            "/api/notifications",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "0" in data["message"]


# ==================== 通知字段测试 ====================

@pytest.mark.asyncio
async def test_notification_response_fields(client, test_user, mock_store):
    """测试通知响应字段完整性"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    notif = mock_store.add_notification(
        user_id=test_user.id,
        task_id="task_001",
        content="这是一条测试通知内容"
    )
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = response.json()
        
        notification = data["notifications"][0]
        assert "id" in notification
        assert notification["id"].startswith("notif_")
        assert notification["task_id"] == "task_001"
        assert notification["content"] == "这是一条测试通知内容"
        assert notification["read"] is False
        assert "created_at" in notification


@pytest.mark.asyncio
async def test_notification_without_task_id(client, test_user, mock_store):
    """测试无关联任务的通知"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    # 手动创建没有 task_id 的通知
    notification_id = "notif_test123"
    notification = {
        "id": notification_id,
        "task_id": None,
        "content": "系统通知",
        "read": False,
        "created_at": datetime.now().isoformat(),
    }
    data = mock_store.load_user_notifications(test_user.id)
    data["notifications"].insert(0, notification)
    mock_store.save_user_notifications(test_user.id, data)
    
    with patch('backend.routers.notifications.get_notification_store', return_value=mock_store):
        response = await client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = response.json()
        
        # task_id 应该为 None
        assert data["notifications"][0]["task_id"] is None