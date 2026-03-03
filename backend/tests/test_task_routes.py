"""
iFlow 对话网页应用 - 定时任务路由测试

测试定时任务的创建、查询、删除、启用/禁用等 API
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.database import get_db, Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from backend.models.user import User
from backend.services.auth import create_access_token, hash_password
from backend.services.scheduler import TaskInfo


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
def mock_task_info():
    """模拟任务信息"""
    return TaskInfo(
        id="task_abc123",
        user_id=1,
        content="提醒我查看股票",
        cron="0 9 * * *",
        natural_language="每天早上9点提醒我查看股票",
        enabled=True,
        created_at="2026-03-03T10:00:00",
        last_run=None,
        next_run="2026-03-04T09:00:00"
    )


# ==================== 获取任务列表测试 ====================

@pytest.mark.asyncio
async def test_get_tasks_empty(client, test_user):
    """测试获取空任务列表"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        mock_scheduler = MagicMock()
        mock_scheduler.get_user_tasks.return_value = []
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tasks"] == []
        mock_scheduler.get_user_tasks.assert_called_once_with(test_user.id)


@pytest.mark.asyncio
async def test_get_tasks_with_data(client, test_user, mock_task_info):
    """测试获取包含任务的列表"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        mock_scheduler = MagicMock()
        mock_scheduler.get_user_tasks.return_value = [mock_task_info]
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["id"] == "task_abc123"
        assert data["tasks"][0]["content"] == "提醒我查看股票"


@pytest.mark.asyncio
async def test_get_tasks_unauthorized(client):
    """测试未授权获取任务列表"""
    response = await client.get("/api/tasks")
    assert response.status_code == 401


# ==================== 创建任务测试 ====================

@pytest.mark.asyncio
async def test_create_task_success(client, test_user, mock_task_info):
    """测试成功创建任务"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_task_parser') as mock_get_parser, \
         patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        
        # 模拟解析器
        mock_parser = MagicMock()
        mock_parsed = MagicMock()
        mock_parsed.success = True
        mock_parsed.content = "提醒我查看股票"
        mock_parsed.cron_expression = "0 9 * * *"
        mock_parser.parse = AsyncMock(return_value=mock_parsed)
        mock_parser.validate_cron.return_value = True
        mock_get_parser.return_value = mock_parser
        
        # 模拟调度器
        mock_scheduler = MagicMock()
        mock_scheduler.add_task.return_value = mock_task_info
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.post(
            "/api/tasks",
            json={"description": "每天早上9点提醒我查看股票"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "任务创建成功"
        assert data["task"]["id"] == "task_abc123"
        mock_parser.parse.assert_called_once_with("每天早上9点提醒我查看股票")
        mock_scheduler.add_task.assert_called_once()


@pytest.mark.asyncio
async def test_create_task_parse_failed(client, test_user):
    """测试解析失败"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_task_parser') as mock_get_parser:
        mock_parser = MagicMock()
        mock_parsed = MagicMock()
        mock_parsed.success = False
        mock_parsed.error = "无法解析任务描述"
        mock_parser.parse = AsyncMock(return_value=mock_parsed)
        mock_get_parser.return_value = mock_parser
        
        response = await client.post(
            "/api/tasks",
            json={"description": "无效描述"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_task_invalid_cron(client, test_user):
    """测试生成的 Cron 表达式无效"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_task_parser') as mock_get_parser:
        mock_parser = MagicMock()
        mock_parsed = MagicMock()
        mock_parsed.success = True
        mock_parsed.content = "测试"
        mock_parsed.cron_expression = "invalid"
        mock_parser.parse = AsyncMock(return_value=mock_parsed)
        mock_parser.validate_cron.return_value = False
        mock_get_parser.return_value = mock_parser
        
        response = await client.post(
            "/api/tasks",
            json={"description": "测试任务"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_task_empty_description(client, test_user):
    """测试空描述"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.post(
        "/api/tasks",
        json={"description": ""},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_task_too_long_description(client, test_user):
    """测试描述过长"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    long_description = "a" * 501
    response = await client.post(
        "/api/tasks",
        json={"description": long_description},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_task_unauthorized(client):
    """测试未授权创建任务"""
    response = await client.post(
        "/api/tasks",
        json={"description": "测试任务"}
    )
    assert response.status_code == 401


# ==================== 删除任务测试 ====================

@pytest.mark.asyncio
async def test_delete_task_success(client, test_user, mock_task_info):
    """测试成功删除任务"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        mock_scheduler = MagicMock()
        mock_scheduler.get_task.return_value = mock_task_info
        mock_scheduler.remove_task.return_value = True
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.delete(
            "/api/tasks/task_abc123",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "任务删除成功"
        mock_scheduler.remove_task.assert_called_once_with(test_user.id, "task_abc123")


@pytest.mark.asyncio
async def test_delete_task_not_found(client, test_user):
    """测试删除不存在的任务"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        mock_scheduler = MagicMock()
        mock_scheduler.get_task.return_value = None
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.delete(
            "/api/tasks/nonexistent",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_task_failed(client, test_user, mock_task_info):
    """测试删除失败"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        mock_scheduler = MagicMock()
        mock_scheduler.get_task.return_value = mock_task_info
        mock_scheduler.remove_task.return_value = False
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.delete(
            "/api/tasks/task_abc123",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


@pytest.mark.asyncio
async def test_delete_task_unauthorized(client):
    """测试未授权删除任务"""
    response = await client.delete("/api/tasks/task_abc123")
    assert response.status_code == 401


# ==================== 切换任务状态测试 ====================

@pytest.mark.asyncio
async def test_toggle_task_enable(client, test_user, mock_task_info):
    """测试启用任务"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    mock_task_info.enabled = False
    enabled_task = TaskInfo(
        id="task_abc123",
        user_id=1,
        content="提醒我查看股票",
        cron="0 9 * * *",
        natural_language="每天早上9点提醒我查看股票",
        enabled=True,
        created_at="2026-03-03T10:00:00",
        last_run=None,
        next_run="2026-03-04T09:00:00"
    )
    
    with patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        mock_scheduler = MagicMock()
        mock_scheduler.get_task.return_value = mock_task_info
        mock_scheduler.toggle_task.return_value = enabled_task
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.put(
            "/api/tasks/task_abc123/toggle",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "任务已启用"
        assert data["task"]["enabled"] is True


@pytest.mark.asyncio
async def test_toggle_task_disable(client, test_user, mock_task_info):
    """测试禁用任务"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    mock_task_info.enabled = True
    disabled_task = TaskInfo(
        id="task_abc123",
        user_id=1,
        content="提醒我查看股票",
        cron="0 9 * * *",
        natural_language="每天早上9点提醒我查看股票",
        enabled=False,
        created_at="2026-03-03T10:00:00",
        last_run=None,
        next_run=None
    )
    
    with patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        mock_scheduler = MagicMock()
        mock_scheduler.get_task.return_value = mock_task_info
        mock_scheduler.toggle_task.return_value = disabled_task
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.put(
            "/api/tasks/task_abc123/toggle",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "任务已禁用"
        assert data["task"]["enabled"] is False


@pytest.mark.asyncio
async def test_toggle_task_not_found(client, test_user):
    """测试切换不存在的任务"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        mock_scheduler = MagicMock()
        mock_scheduler.get_task.return_value = None
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.put(
            "/api/tasks/nonexistent/toggle",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_toggle_task_failed(client, test_user, mock_task_info):
    """测试切换失败"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        mock_scheduler = MagicMock()
        mock_scheduler.get_task.return_value = mock_task_info
        mock_scheduler.toggle_task.return_value = None
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.put(
            "/api/tasks/task_abc123/toggle",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 500


@pytest.mark.asyncio
async def test_toggle_task_unauthorized(client):
    """测试未授权切换任务"""
    response = await client.put("/api/tasks/task_abc123/toggle")
    assert response.status_code == 401


# ==================== 边界情况测试 ====================

@pytest.mark.asyncio
async def test_multiple_tasks(client, test_user):
    """测试多个任务"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    tasks = [
        TaskInfo(
            id=f"task_{i}",
            user_id=test_user.id,
            content=f"任务{i}",
            cron="0 9 * * *",
            natural_language=f"每天任务{i}",
            enabled=True,
            created_at="2026-03-03T10:00:00"
        )
        for i in range(5)
    ]
    
    with patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        mock_scheduler = MagicMock()
        mock_scheduler.get_user_tasks.return_value = tasks
        mock_get_scheduler.return_value = mock_scheduler
        
        response = await client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 5


@pytest.mark.asyncio
async def test_create_task_with_special_characters(client, test_user, mock_task_info):
    """测试包含特殊字符的描述"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    with patch('backend.routers.tasks.get_task_parser') as mock_get_parser, \
         patch('backend.routers.tasks.get_scheduler') as mock_get_scheduler:
        
        mock_parser = MagicMock()
        mock_parsed = MagicMock()
        mock_parsed.success = True
        mock_parsed.content = "提醒我查看股票"
        mock_parsed.cron_expression = "0 9 * * *"
        mock_parser.parse = AsyncMock(return_value=mock_parsed)
        mock_parser.validate_cron.return_value = True
        mock_get_parser.return_value = mock_parser
        
        mock_scheduler = MagicMock()
        mock_scheduler.add_task.return_value = mock_task_info
        mock_get_scheduler.return_value = mock_scheduler
        
        # 包含中文、表情符号等
        response = await client.post(
            "/api/tasks",
            json={"description": "每天早上9点提醒我查看股票 📈"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200