"""
iFlow 对话网页应用 - 定时任务流程集成测试

测试完整的定时任务流程：
- 自然语言创建任务
- 任务列表查询
- 任务启用/禁用
- 任务删除
- 任务定时执行
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

from backend.database import get_db, Base
from backend.models.user import User
from backend.services.auth import create_access_token, hash_password
from backend.services.scheduler import (
    TaskInfo,
    TaskStore,
    TaskScheduler,
    get_scheduler,
)
from backend.services.task_parser import ParsedTask
from backend.services.task_executor import TaskExecutor, NotificationStore
from backend.routers import tasks, notifications


# ==================== 创建测试应用（不包含 scheduler lifespan） ====================

def create_test_app():
    """创建测试用 FastAPI 应用（不包含 scheduler lifespan）"""
    test_app = FastAPI(
        title="iFlow Task API (Test)",
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
    test_app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
    test_app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
    
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
def temp_dirs():
    """创建临时目录（任务和通知存储）"""
    with tempfile.TemporaryDirectory() as tasks_dir:
        with tempfile.TemporaryDirectory() as notifications_dir:
            yield {"tasks_dir": tasks_dir, "notifications_dir": notifications_dir}


@pytest.fixture(scope="function")
async def client(db_session, temp_dirs):
    """创建测试客户端"""
    test_app = create_test_app()
    
    async def override_get_db():
        yield db_session
    
    test_app.dependency_overrides[get_db] = override_get_db
    
    # Mock scheduler
    scheduler = TaskScheduler()
    scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
    
    with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    
    test_app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """创建测试用户"""
    user = User(
        username="taskuser",
        email="task@example.com",
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


# ==================== 自然语言创建任务测试 ====================

@pytest.mark.asyncio
class TestCreateTaskWithNaturalLanguage:
    """自然语言创建任务集成测试"""
    
    async def test_create_task_daily_schedule(self, client, test_user, auth_headers, temp_dirs):
        """测试创建每天定时任务"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        # Mock 解析器返回成功结果
        parsed = ParsedTask(
            success=True,
            content="提醒我查看股票",
            cron_expression="0 9 * * *",
            task_type="daily",
            time_info={"hour": 9, "minute": 0},
            natural_language="每天早上9点提醒我查看股票",
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler), \
             patch('backend.routers.tasks.get_task_parser') as mock_get_parser:
            
            mock_parser = MagicMock()
            mock_parser.parse = AsyncMock(return_value=parsed)
            mock_parser.validate_cron = MagicMock(return_value=True)
            mock_get_parser.return_value = mock_parser
            
            response = await client.post(
                "/api/tasks",
                json={"description": "每天早上9点提醒我查看股票"},
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "任务创建成功"
        assert data["task"]["content"] == "提醒我查看股票"
        assert data["task"]["cron"] == "0 9 * * *"
        assert data["task"]["enabled"] is True
    
    async def test_create_task_weekly_schedule(self, client, test_user, auth_headers, temp_dirs):
        """测试创建每周定时任务"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        parsed = ParsedTask(
            success=True,
            content="提交周报",
            cron_expression="0 17 * * 5",
            task_type="weekly",
            time_info={"hour": 17, "minute": 0, "weekday": 5},
            natural_language="每周五下午5点提交周报",
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler), \
             patch('backend.routers.tasks.get_task_parser') as mock_get_parser:
            
            mock_parser = MagicMock()
            mock_parser.parse = AsyncMock(return_value=parsed)
            mock_parser.validate_cron = MagicMock(return_value=True)
            mock_get_parser.return_value = mock_parser
            
            response = await client.post(
                "/api/tasks",
                json={"description": "每周五下午5点提交周报"},
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task"]["cron"] == "0 17 * * 5"
    
    async def test_create_task_monthly_schedule(self, client, test_user, auth_headers, temp_dirs):
        """测试创建每月定时任务"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        parsed = ParsedTask(
            success=True,
            content="检查账单",
            cron_expression="0 10 1 * *",
            task_type="monthly",
            time_info={"hour": 10, "minute": 0, "day_of_month": 1},
            natural_language="每月1号上午10点检查账单",
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler), \
             patch('backend.routers.tasks.get_task_parser') as mock_get_parser:
            
            mock_parser = MagicMock()
            mock_parser.parse = AsyncMock(return_value=parsed)
            mock_parser.validate_cron = MagicMock(return_value=True)
            mock_get_parser.return_value = mock_parser
            
            response = await client.post(
                "/api/tasks",
                json={"description": "每月1号上午10点检查账单"},
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task"]["cron"] == "0 10 1 * *"
    
    async def test_create_task_parse_failed(self, client, test_user, auth_headers, temp_dirs):
        """测试解析失败"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        parsed = ParsedTask(
            success=False,
            error="无法理解任务描述",
            content="",
            cron_expression="",
            task_type="",
            time_info={},
            natural_language="无效描述",
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler), \
             patch('backend.routers.tasks.get_task_parser') as mock_get_parser:
            
            mock_parser = MagicMock()
            mock_parser.parse = AsyncMock(return_value=parsed)
            mock_get_parser.return_value = mock_parser
            
            response = await client.post(
                "/api/tasks",
                json={"description": "无效描述"},
                headers=auth_headers
            )
        
        assert response.status_code == 400
    
    async def test_create_task_invalid_cron(self, client, test_user, auth_headers, temp_dirs):
        """测试生成的 Cron 表达式无效"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        parsed = ParsedTask(
            success=True,
            content="测试",
            cron_expression="invalid",
            task_type="unknown",
            time_info={},
            natural_language="测试",
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler), \
             patch('backend.routers.tasks.get_task_parser') as mock_get_parser:
            
            mock_parser = MagicMock()
            mock_parser.parse = AsyncMock(return_value=parsed)
            mock_parser.validate_cron = MagicMock(return_value=False)
            mock_get_parser.return_value = mock_parser
            
            response = await client.post(
                "/api/tasks",
                json={"description": "测试"},
                headers=auth_headers
            )
        
        assert response.status_code == 400
    
    async def test_create_task_unauthorized(self, client):
        """测试未授权创建任务"""
        response = await client.post(
            "/api/tasks",
            json={"description": "每天早上9点提醒我"}
        )
        assert response.status_code == 401
    
    async def test_create_task_empty_description(self, client, test_user, auth_headers, temp_dirs):
        """测试空描述"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.post(
                "/api/tasks",
                json={"description": ""},
                headers=auth_headers
            )
        
        assert response.status_code == 422  # Validation error


# ==================== 任务列表查询测试 ====================

@pytest.mark.asyncio
class TestTaskListQuery:
    """任务列表查询集成测试"""
    
    async def test_get_empty_task_list(self, client, test_user, auth_headers, temp_dirs):
        """测试获取空任务列表"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.get("/api/tasks", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tasks"] == []
    
    async def test_get_task_list_with_tasks(self, client, test_user, auth_headers, temp_dirs):
        """测试获取包含任务的列表"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        # 添加任务
        task1 = scheduler.add_task(
            user_id=test_user.id,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点查看股票",
        )
        task2 = scheduler.add_task(
            user_id=test_user.id,
            content="查看天气",
            cron="0 8 * * *",
            natural_language="每天早上8点查看天气",
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.get("/api/tasks", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["tasks"]) == 2
    
    async def test_task_list_user_isolation(self, client, test_user, auth_headers, temp_dirs, db_session):
        """测试任务列表用户隔离"""
        # 创建另一个用户
        other_user = User(
            username="otheruser",
            email="other@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        # 为当前用户添加任务
        scheduler.add_task(
            user_id=test_user.id,
            content="当前用户的任务",
            cron="0 9 * * *",
            natural_language="当前用户任务",
        )
        
        # 为其他用户添加任务
        scheduler.add_task(
            user_id=other_user.id,
            content="其他用户的任务",
            cron="0 10 * * *",
            natural_language="其他用户任务",
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.get("/api/tasks", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["content"] == "当前用户的任务"
    
    async def test_task_list_unauthorized(self, client):
        """测试未授权获取任务列表"""
        response = await client.get("/api/tasks")
        assert response.status_code == 401
    
    async def test_task_list_order(self, client, test_user, auth_headers, temp_dirs):
        """测试任务列表顺序"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        # 添加多个任务
        for i in range(3):
            scheduler.add_task(
                user_id=test_user.id,
                content=f"任务_{i}",
                cron="0 9 * * *",
                natural_language=f"任务_{i}",
            )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.get("/api/tasks", headers=auth_headers)
        
        assert response.status_code == 200
        tasks = response.json()["tasks"]
        assert len(tasks) == 3


# ==================== 任务启用/禁用测试 ====================

@pytest.mark.asyncio
class TestTaskToggle:
    """任务启用/禁用集成测试"""
    
    async def test_toggle_task_enable(self, client, test_user, auth_headers, temp_dirs):
        """测试启用任务"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        # 创建禁用的任务
        task = scheduler.add_task(
            user_id=test_user.id,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点查看股票",
            enabled=False,
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.put(
                f"/api/tasks/{task.id}/toggle",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "任务已启用"
        assert data["task"]["enabled"] is True
    
    async def test_toggle_task_disable(self, client, test_user, auth_headers, temp_dirs):
        """测试禁用任务"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        # 创建启用的任务
        task = scheduler.add_task(
            user_id=test_user.id,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点查看股票",
            enabled=True,
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.put(
                f"/api/tasks/{task.id}/toggle",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "任务已禁用"
        assert data["task"]["enabled"] is False
    
    async def test_toggle_task_multiple_times(self, client, test_user, auth_headers, temp_dirs):
        """测试多次切换任务状态"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        task = scheduler.add_task(
            user_id=test_user.id,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点查看股票",
            enabled=True,
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            # 第一次切换 -> 禁用
            response1 = await client.put(
                f"/api/tasks/{task.id}/toggle",
                headers=auth_headers
            )
            assert response1.json()["task"]["enabled"] is False
            
            # 第二次切换 -> 启用
            response2 = await client.put(
                f"/api/tasks/{task.id}/toggle",
                headers=auth_headers
            )
            assert response2.json()["task"]["enabled"] is True
            
            # 第三次切换 -> 禁用
            response3 = await client.put(
                f"/api/tasks/{task.id}/toggle",
                headers=auth_headers
            )
            assert response3.json()["task"]["enabled"] is False
    
    async def test_toggle_task_not_found(self, client, test_user, auth_headers, temp_dirs):
        """测试切换不存在的任务"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.put(
                "/api/tasks/nonexistent_task/toggle",
                headers=auth_headers
            )
        
        assert response.status_code == 404
    
    async def test_toggle_task_unauthorized(self, client):
        """测试未授权切换任务"""
        response = await client.put("/api/tasks/task_001/toggle")
        assert response.status_code == 401


# ==================== 任务删除测试 ====================

@pytest.mark.asyncio
class TestTaskDelete:
    """任务删除集成测试"""
    
    async def test_delete_task_success(self, client, test_user, auth_headers, temp_dirs):
        """测试成功删除任务"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        task = scheduler.add_task(
            user_id=test_user.id,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点查看股票",
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.delete(
                f"/api/tasks/{task.id}",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "任务删除成功"
        
        # 验证任务已删除
        deleted_task = scheduler.get_task(test_user.id, task.id)
        assert deleted_task is None
    
    async def test_delete_task_not_found(self, client, test_user, auth_headers, temp_dirs):
        """测试删除不存在的任务"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.delete(
                "/api/tasks/nonexistent_task",
                headers=auth_headers
            )
        
        assert response.status_code == 404
    
    async def test_delete_task_twice(self, client, test_user, auth_headers, temp_dirs):
        """测试重复删除任务"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        task = scheduler.add_task(
            user_id=test_user.id,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点查看股票",
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            # 第一次删除
            response1 = await client.delete(
                f"/api/tasks/{task.id}",
                headers=auth_headers
            )
            assert response1.status_code == 200
            
            # 第二次删除
            response2 = await client.delete(
                f"/api/tasks/{task.id}",
                headers=auth_headers
            )
            assert response2.status_code == 404
    
    async def test_delete_task_unauthorized(self, client):
        """测试未授权删除任务"""
        response = await client.delete("/api/tasks/task_001")
        assert response.status_code == 401
    
    async def test_delete_task_user_isolation(self, client, test_user, auth_headers, temp_dirs, db_session):
        """测试删除任务用户隔离"""
        # 创建另一个用户
        other_user = User(
            username="otheruser",
            email="other@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        # 为其他用户添加任务
        other_task = scheduler.add_task(
            user_id=other_user.id,
            content="其他用户的任务",
            cron="0 10 * * *",
            natural_language="其他用户任务",
        )
        
        # 尝试用当前用户的 token 删除其他用户的任务
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler):
            response = await client.delete(
                f"/api/tasks/{other_task.id}",
                headers=auth_headers
            )
        
        # 应该返回 404（任务不存在于当前用户）
        assert response.status_code == 404
        
        # 验证其他用户的任务仍然存在
        still_exists = scheduler.get_task(other_user.id, other_task.id)
        assert still_exists is not None


# ==================== 任务定时执行测试 ====================

@pytest.mark.asyncio
class TestTaskExecution:
    """任务定时执行集成测试"""
    
    async def test_execute_task_saves_notification(self, temp_dirs):
        """测试执行任务保存通知"""
        notification_store = NotificationStore(
            notifications_dir=temp_dirs["notifications_dir"]
        )
        
        # Mock WebSocket 管理器
        mock_ws_manager = MagicMock()
        mock_ws_manager.is_user_online.return_value = False
        
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=mock_ws_manager,
        )
        
        # Mock iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "今日股票上涨 2%"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        assert result["success"] is True
        assert result["notification"] is not None
        
        # 验证通知已保存
        notifications = notification_store.get_notifications(user_id=1)
        assert len(notifications["notifications"]) == 1
        assert "查看股票" in notifications["notifications"][0]["content"]
    
    async def test_execute_task_pushes_to_online_user(self, temp_dirs):
        """测试在线用户收到推送"""
        notification_store = NotificationStore(
            notifications_dir=temp_dirs["notifications_dir"]
        )
        
        # Mock WebSocket 管理器 - 用户在线
        mock_ws_manager = MagicMock()
        mock_ws_manager.is_user_online.return_value = True
        mock_ws_manager.send_to_user = AsyncMock(return_value=1)
        
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=mock_ws_manager,
        )
        
        # Mock iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "响应内容"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        assert result["success"] is True
        assert result["pushed"] is True
        
        # 验证推送被调用
        mock_ws_manager.send_to_user.assert_called_once()
    
    async def test_execute_task_no_push_for_offline_user(self, temp_dirs):
        """测试离线用户不收到推送"""
        notification_store = NotificationStore(
            notifications_dir=temp_dirs["notifications_dir"]
        )
        
        # Mock WebSocket 管理器 - 用户离线
        mock_ws_manager = MagicMock()
        mock_ws_manager.is_user_online.return_value = False
        mock_ws_manager.send_to_user = AsyncMock()
        
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=mock_ws_manager,
        )
        
        # Mock iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "响应内容"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        assert result["success"] is True
        assert result["pushed"] is False
        
        # 验证推送未被调用
        mock_ws_manager.send_to_user.assert_not_called()
    
    async def test_execute_task_handles_iflow_error(self, temp_dirs):
        """测试处理 iFlow 错误"""
        notification_store = NotificationStore(
            notifications_dir=temp_dirs["notifications_dir"]
        )
        
        mock_ws_manager = MagicMock()
        mock_ws_manager.is_user_online.return_value = False
        
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=mock_ws_manager,
        )
        
        # Mock iFlow 抛出异常
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.side_effect = Exception("iFlow 连接失败")
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        assert result["success"] is False
        assert "iFlow 连接失败" in result["error"]
        
        # 验证失败通知已保存
        assert result["notification"] is not None
        assert "执行失败" in result["notification"]["content"]
    
    async def test_execute_multiple_tasks(self, temp_dirs):
        """测试执行多个任务"""
        notification_store = NotificationStore(
            notifications_dir=temp_dirs["notifications_dir"]
        )
        
        mock_ws_manager = MagicMock()
        mock_ws_manager.is_user_online.return_value = False
        
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=mock_ws_manager,
        )
        
        # Mock iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "响应"
            
            # 执行多个任务
            for i in range(3):
                await executor.execute_task(
                    user_id=1,
                    task_id=f"task_{i}",
                    content=f"任务_{i}"
                )
        
        # 验证所有通知已保存
        notifications = notification_store.get_notifications(user_id=1)
        assert len(notifications["notifications"]) == 3
    
    async def test_task_execution_with_scheduler(self, temp_dirs):
        """测试调度器触发任务执行"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        # 添加任务
        task = scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点查看股票",
        )
        
        # 设置回调
        callback_results = []
        
        async def test_callback(user_id, task_id, content):
            callback_results.append({
                'user_id': user_id,
                'task_id': task_id,
                'content': content
            })
        
        scheduler.set_task_callback(test_callback)
        
        # 手动触发执行
        await scheduler._execute_task(1, task.id, "查看股票")
        
        assert len(callback_results) == 1
        assert callback_results[0]['content'] == "查看股票"
        
        # 验证最后执行时间已更新
        updated_task = scheduler.get_task(1, task.id)
        assert updated_task.last_run is not None


# ==================== 完整流程集成测试 ====================

@pytest.mark.asyncio
class TestFullTaskFlow:
    """完整任务流程集成测试"""
    
    async def test_full_task_lifecycle(self, client, test_user, auth_headers, temp_dirs):
        """测试完整任务生命周期：创建 -> 查询 -> 切换 -> 删除"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        parsed = ParsedTask(
            success=True,
            content="提醒我查看股票",
            cron_expression="0 9 * * *",
            task_type="daily",
            time_info={"hour": 9, "minute": 0},
            natural_language="每天早上9点提醒我查看股票",
        )
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler), \
             patch('backend.routers.tasks.get_task_parser') as mock_get_parser:
            
            mock_parser = MagicMock()
            mock_parser.parse = AsyncMock(return_value=parsed)
            mock_parser.validate_cron = MagicMock(return_value=True)
            mock_get_parser.return_value = mock_parser
            
            # Step 1: 创建任务
            create_response = await client.post(
                "/api/tasks",
                json={"description": "每天早上9点提醒我查看股票"},
                headers=auth_headers
            )
            assert create_response.status_code == 200
            task_id = create_response.json()["task"]["id"]
            
            # Step 2: 查询任务列表
            list_response = await client.get("/api/tasks", headers=auth_headers)
            assert list_response.status_code == 200
            assert len(list_response.json()["tasks"]) == 1
            
            # Step 3: 切换任务状态
            toggle_response = await client.put(
                f"/api/tasks/{task_id}/toggle",
                headers=auth_headers
            )
            assert toggle_response.status_code == 200
            assert toggle_response.json()["task"]["enabled"] is False
            
            # Step 4: 再次切换恢复启用
            toggle_response2 = await client.put(
                f"/api/tasks/{task_id}/toggle",
                headers=auth_headers
            )
            assert toggle_response2.json()["task"]["enabled"] is True
            
            # Step 5: 删除任务
            delete_response = await client.delete(
                f"/api/tasks/{task_id}",
                headers=auth_headers
            )
            assert delete_response.status_code == 200
            
            # Step 6: 验证任务已删除
            final_list = await client.get("/api/tasks", headers=auth_headers)
            assert len(final_list.json()["tasks"]) == 0
    
    async def test_multiple_tasks_management(self, client, test_user, auth_headers, temp_dirs):
        """测试多任务管理"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dirs["tasks_dir"])
        
        with patch('backend.routers.tasks.get_scheduler', return_value=scheduler), \
             patch('backend.routers.tasks.get_task_parser') as mock_get_parser:
            
            mock_parser = MagicMock()
            mock_parser.validate_cron = MagicMock(return_value=True)
            mock_get_parser.return_value = mock_parser
            
            # 创建 3 个任务
            task_ids = []
            for i in range(3):
                parsed = ParsedTask(
                    success=True,
                    content=f"任务_{i}",
                    cron_expression=f"0 {9+i} * * *",
                    task_type="daily",
                    time_info={"hour": 9+i, "minute": 0},
                    natural_language=f"任务_{i}",
                )
                mock_parser.parse = AsyncMock(return_value=parsed)
                
                response = await client.post(
                    "/api/tasks",
                    json={"description": f"任务_{i}"},
                    headers=auth_headers
                )
                assert response.status_code == 200
                task_ids.append(response.json()["task"]["id"])
            
            # 验证 3 个任务
            list_response = await client.get("/api/tasks", headers=auth_headers)
            assert len(list_response.json()["tasks"]) == 3
            
            # 禁用第二个任务
            toggle_response = await client.put(
                f"/api/tasks/{task_ids[1]}/toggle",
                headers=auth_headers
            )
            assert toggle_response.json()["task"]["enabled"] is False
            
            # 删除第一个任务
            delete_response = await client.delete(
                f"/api/tasks/{task_ids[0]}",
                headers=auth_headers
            )
            assert delete_response.status_code == 200
            
            # 验证剩余 2 个任务
            final_list = await client.get("/api/tasks", headers=auth_headers)
            assert len(final_list.json()["tasks"]) == 2
    
    async def test_task_execution_and_notification_flow(self, temp_dirs):
        """测试任务执行和通知流程"""
        notification_store = NotificationStore(
            notifications_dir=temp_dirs["notifications_dir"]
        )
        
        mock_ws_manager = MagicMock()
        mock_ws_manager.is_user_online.return_value = True
        mock_ws_manager.send_to_user = AsyncMock(return_value=1)
        
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=mock_ws_manager,
        )
        
        # Mock iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "今日上证指数 3000 点"
            
            # 执行任务
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票行情"
            )
        
        # 验证执行结果
        assert result["success"] is True
        assert result["pushed"] is True
        
        # 验证通知已保存
        notifications = notification_store.get_notifications(user_id=1)
        assert len(notifications["notifications"]) == 1
        assert notifications["unread_count"] == 1
        
        # 验证 WebSocket 推送
        mock_ws_manager.send_to_user.assert_called_once()
        call_args = mock_ws_manager.send_to_user.call_args
        message = call_args[0][1]
        assert message["type"] == "notification"