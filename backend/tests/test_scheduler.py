"""
定时任务调度器测试
"""
import pytest
import asyncio
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.scheduler import (
    TaskInfo,
    TaskStore,
    TaskScheduler,
    get_scheduler,
    start_scheduler,
    shutdown_scheduler,
)


class TestTaskInfo:
    """TaskInfo 数据类测试"""
    
    def test_task_info_creation(self):
        """测试创建任务信息"""
        task = TaskInfo(
            id="task_001",
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票",
            enabled=True,
            created_at="2026-03-03T10:00:00"
        )
        
        assert task.id == "task_001"
        assert task.user_id == 1
        assert task.content == "查看股票"
        assert task.cron == "0 9 * * *"
        assert task.enabled is True
    
    def test_task_info_to_dict(self):
        """测试转换为字典"""
        task = TaskInfo(
            id="task_001",
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票",
            enabled=True,
            created_at="2026-03-03T10:00:00"
        )
        
        result = task.to_dict()
        
        assert isinstance(result, dict)
        assert result["id"] == "task_001"
        assert result["user_id"] == 1
        assert result["content"] == "查看股票"
    
    def test_task_info_from_dict(self):
        """测试从字典创建"""
        data = {
            "id": "task_001",
            "user_id": 1,
            "content": "查看股票",
            "cron": "0 9 * * *",
            "natural_language": "每天早上9点提醒我查看股票",
            "enabled": True,
            "created_at": "2026-03-03T10:00:00",
            "last_run": None,
            "next_run": None
        }
        
        task = TaskInfo.from_dict(data)
        
        assert task.id == "task_001"
        assert task.user_id == 1
        assert task.content == "查看股票"


class TestTaskStore:
    """TaskStore 存储测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def task_store(self, temp_dir):
        """创建任务存储实例"""
        return TaskStore(tasks_dir=temp_dir)
    
    def test_ensure_dir_created(self, task_store, temp_dir):
        """测试目录创建"""
        assert os.path.exists(temp_dir)
    
    def test_get_user_file_path(self, task_store, temp_dir):
        """测试用户文件路径"""
        path = task_store._get_user_file(1)
        assert path == os.path.join(temp_dir, "1.json")
    
    def test_load_empty_tasks(self, task_store):
        """测试加载空任务列表"""
        tasks = task_store.load_user_tasks(1)
        assert tasks == []
    
    def test_save_and_load_tasks(self, task_store):
        """测试保存和加载任务"""
        task = TaskInfo(
            id="task_001",
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票",
            enabled=True,
            created_at="2026-03-03T10:00:00"
        )
        
        # 保存任务
        task_store.add_task(1, task)
        
        # 加载任务
        tasks = task_store.load_user_tasks(1)
        
        assert len(tasks) == 1
        assert tasks[0].id == "task_001"
        assert tasks[0].content == "查看股票"
    
    def test_add_multiple_tasks(self, task_store):
        """测试添加多个任务"""
        task1 = TaskInfo(
            id="task_001",
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票",
            enabled=True,
            created_at="2026-03-03T10:00:00"
        )
        
        task2 = TaskInfo(
            id="task_002",
            user_id=1,
            content="查看天气",
            cron="0 8 * * *",
            natural_language="每天早上8点提醒我查看天气",
            enabled=True,
            created_at="2026-03-03T10:00:00"
        )
        
        task_store.add_task(1, task1)
        task_store.add_task(1, task2)
        
        tasks = task_store.load_user_tasks(1)
        assert len(tasks) == 2
    
    def test_update_task(self, task_store):
        """测试更新任务"""
        task = TaskInfo(
            id="task_001",
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票",
            enabled=True,
            created_at="2026-03-03T10:00:00"
        )
        
        task_store.add_task(1, task)
        
        # 更新任务
        task.content = "查看基金"
        task.enabled = False
        result = task_store.update_task(1, task)
        
        assert result is True
        
        # 验证更新
        updated_task = task_store.get_task(1, "task_001")
        assert updated_task.content == "查看基金"
        assert updated_task.enabled is False
    
    def test_update_nonexistent_task(self, task_store):
        """测试更新不存在的任务"""
        task = TaskInfo(
            id="task_999",
            user_id=1,
            content="测试",
            cron="0 9 * * *",
            natural_language="测试",
            enabled=True,
            created_at="2026-03-03T10:00:00"
        )
        
        result = task_store.update_task(1, task)
        assert result is False
    
    def test_delete_task(self, task_store):
        """测试删除任务"""
        task = TaskInfo(
            id="task_001",
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票",
            enabled=True,
            created_at="2026-03-03T10:00:00"
        )
        
        task_store.add_task(1, task)
        
        # 删除任务
        result = task_store.delete_task(1, "task_001")
        assert result is True
        
        # 验证删除
        tasks = task_store.load_user_tasks(1)
        assert len(tasks) == 0
    
    def test_delete_nonexistent_task(self, task_store):
        """测试删除不存在的任务"""
        result = task_store.delete_task(1, "task_999")
        assert result is False
    
    def test_get_task(self, task_store):
        """测试获取单个任务"""
        task = TaskInfo(
            id="task_001",
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票",
            enabled=True,
            created_at="2026-03-03T10:00:00"
        )
        
        task_store.add_task(1, task)
        
        # 获取任务
        found_task = task_store.get_task(1, "task_001")
        assert found_task is not None
        assert found_task.id == "task_001"
    
    def test_get_nonexistent_task(self, task_store):
        """测试获取不存在的任务"""
        task = task_store.get_task(1, "task_999")
        assert task is None
    
    def test_load_corrupted_json(self, task_store, temp_dir):
        """测试加载损坏的 JSON 文件"""
        # 创建损坏的 JSON 文件
        file_path = os.path.join(temp_dir, "1.json")
        with open(file_path, 'w') as f:
            f.write("invalid json {")
        
        # 应该返回空列表
        tasks = task_store.load_user_tasks(1)
        assert tasks == []


class TestTaskScheduler:
    """TaskScheduler 调度器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def scheduler(self, temp_dir):
        """创建调度器实例"""
        sched = TaskScheduler()
        sched.task_store = TaskStore(tasks_dir=temp_dir)
        return sched
    
    def test_generate_task_id(self, scheduler):
        """测试生成任务 ID"""
        id1 = scheduler.generate_task_id()
        id2 = scheduler.generate_task_id()
        
        assert id1.startswith("task_")
        assert id2.startswith("task_")
        assert id1 != id2  # 唯一性
    
    def test_add_task(self, scheduler):
        """测试添加任务"""
        task = scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票"
        )
        
        assert task.id.startswith("task_")
        assert task.user_id == 1
        assert task.content == "查看股票"
        assert task.enabled is True
        
        # 验证已保存
        saved_task = scheduler.get_task(1, task.id)
        assert saved_task is not None
    
    def test_add_disabled_task(self, scheduler):
        """测试添加禁用的任务"""
        task = scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票",
            enabled=False
        )
        
        assert task.enabled is False
    
    def test_remove_task(self, scheduler):
        """测试删除任务"""
        task = scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票"
        )
        
        # 删除任务
        result = scheduler.remove_task(1, task.id)
        assert result is True
        
        # 验证已删除
        deleted_task = scheduler.get_task(1, task.id)
        assert deleted_task is None
    
    def test_remove_nonexistent_task(self, scheduler):
        """测试删除不存在的任务"""
        result = scheduler.remove_task(1, "task_999")
        assert result is False
    
    def test_enable_task(self, scheduler):
        """测试启用任务"""
        task = scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票",
            enabled=False
        )
        
        # 启用任务
        result = scheduler.enable_task(1, task.id)
        assert result is True
        
        # 验证状态
        enabled_task = scheduler.get_task(1, task.id)
        assert enabled_task.enabled is True
    
    def test_disable_task(self, scheduler):
        """测试禁用任务"""
        task = scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票"
        )
        
        # 禁用任务
        result = scheduler.disable_task(1, task.id)
        assert result is True
        
        # 验证状态
        disabled_task = scheduler.get_task(1, task.id)
        assert disabled_task.enabled is False
    
    def test_toggle_task(self, scheduler):
        """测试切换任务状态"""
        task = scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票",
            enabled=True
        )
        
        # 切换为禁用
        toggled_task = scheduler.toggle_task(1, task.id)
        assert toggled_task.enabled is False
        
        # 再次切换为启用
        toggled_task = scheduler.toggle_task(1, task.id)
        assert toggled_task.enabled is True
    
    def test_toggle_nonexistent_task(self, scheduler):
        """测试切换不存在的任务"""
        result = scheduler.toggle_task(1, "task_999")
        assert result is None
    
    def test_get_user_tasks(self, scheduler):
        """测试获取用户任务列表"""
        scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票"
        )
        
        scheduler.add_task(
            user_id=1,
            content="查看天气",
            cron="0 8 * * *",
            natural_language="每天早上8点提醒我查看天气"
        )
        
        tasks = scheduler.get_user_tasks(1)
        assert len(tasks) == 2
    
    def test_get_task(self, scheduler):
        """测试获取单个任务"""
        task = scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票"
        )
        
        found_task = scheduler.get_task(1, task.id)
        assert found_task is not None
        assert found_task.content == "查看股票"
    
    def test_set_task_callback(self, scheduler):
        """测试设置任务回调"""
        callback_called = False
        
        async def test_callback(user_id, task_id, content):
            nonlocal callback_called
            callback_called = True
        
        scheduler.set_task_callback(test_callback)
        assert 'default' in scheduler._task_callbacks
    
    def test_scheduler_start_and_shutdown(self, scheduler):
        """测试调度器启动和关闭"""
        scheduler.start()
        assert scheduler._is_running is True
        
        scheduler.shutdown()
        assert scheduler._is_running is False
    
    def test_reload_user_tasks(self, scheduler):
        """测试重新加载用户任务"""
        # 添加任务
        task = scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票"
        )
        
        # 启动调度器
        scheduler.start()
        
        # 重新加载任务
        scheduler.reload_user_tasks(1)
        
        # 验证任务已加载到调度器
        job = scheduler.scheduler.get_job(task.id)
        assert job is not None
        
        scheduler.shutdown()
    
    def test_reload_all_tasks(self, scheduler):
        """测试重新加载所有任务"""
        # 添加多个用户的任务
        scheduler.add_task(
            user_id=1,
            content="任务1",
            cron="0 9 * * *",
            natural_language="任务1"
        )
        
        scheduler.add_task(
            user_id=2,
            content="任务2",
            cron="0 10 * * *",
            natural_language="任务2"
        )
        
        # 启动调度器
        scheduler.start()
        
        # 重新加载所有任务
        scheduler.reload_all_tasks()
        
        scheduler.shutdown()


class TestGlobalScheduler:
    """全局调度器测试"""
    
    def test_get_scheduler_singleton(self):
        """测试获取调度器单例"""
        # 清除之前的状态
        import backend.services.scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()
        
        assert scheduler1 is scheduler2
    
    def test_start_and_shutdown_scheduler(self):
        """测试启动和关闭全局调度器"""
        # 清除之前的状态
        import backend.services.scheduler as scheduler_module
        scheduler_module._scheduler = None
        
        start_scheduler()
        
        scheduler = get_scheduler()
        assert scheduler._is_running is True
        
        shutdown_scheduler()
        assert scheduler._is_running is False


class TestTaskExecution:
    """任务执行测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.mark.asyncio
    async def test_execute_task_with_callback(self, temp_dir):
        """测试执行任务回调"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dir)
        
        callback_results = []
        
        async def test_callback(user_id, task_id, content):
            callback_results.append({
                'user_id': user_id,
                'task_id': task_id,
                'content': content
            })
        
        scheduler.set_task_callback(test_callback)
        
        # 执行任务
        await scheduler._execute_task(1, "task_001", "测试内容")
        
        assert len(callback_results) == 1
        assert callback_results[0]['user_id'] == 1
        assert callback_results[0]['content'] == "测试内容"
    
    @pytest.mark.asyncio
    async def test_execute_task_updates_last_run(self, temp_dir):
        """测试执行任务更新最后执行时间"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dir)
        
        # 添加任务
        task = scheduler.add_task(
            user_id=1,
            content="查看股票",
            cron="0 9 * * *",
            natural_language="每天早上9点提醒我查看股票"
        )
        
        # 执行任务
        await scheduler._execute_task(1, task.id, "查看股票")
        
        # 验证最后执行时间已更新
        updated_task = scheduler.get_task(1, task.id)
        assert updated_task.last_run is not None
    
    @pytest.mark.asyncio
    async def test_execute_task_with_sync_callback(self, temp_dir):
        """测试执行同步回调函数"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dir)
        
        callback_results = []
        
        def sync_callback(user_id, task_id, content):
            callback_results.append(content)
        
        scheduler.set_task_callback(sync_callback)
        
        # 执行任务
        await scheduler._execute_task(1, "task_001", "测试内容")
        
        assert len(callback_results) == 1
        assert callback_results[0] == "测试内容"
    
    @pytest.mark.asyncio
    async def test_execute_task_handles_exception(self, temp_dir):
        """测试执行任务处理异常"""
        scheduler = TaskScheduler()
        scheduler.task_store = TaskStore(tasks_dir=temp_dir)
        
        async def failing_callback(user_id, task_id, content):
            raise ValueError("测试异常")
        
        scheduler.set_task_callback(failing_callback)
        
        # 执行任务（不应抛出异常）
        await scheduler._execute_task(1, "task_001", "测试内容")
        
        # 任务应该正常完成，异常被捕获


class TestCronExpression:
    """Cron 表达式测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def scheduler(self, temp_dir):
        """创建调度器实例"""
        sched = TaskScheduler()
        sched.task_store = TaskStore(tasks_dir=temp_dir)
        return sched
    
    def test_valid_cron_expression(self, scheduler):
        """测试有效的 Cron 表达式"""
        # 各种有效的 Cron 表达式
        valid_crons = [
            "0 9 * * *",       # 每天 9:00
            "*/15 * * * *",    # 每 15 分钟
            "0 0 1 * *",       # 每月 1 日 0:00
            "0 9 * * 1",       # 每周一 9:00
            "0 9 1 1 *",       # 每年 1 月 1 日 9:00
        ]
        
        for cron in valid_crons:
            task = scheduler.add_task(
                user_id=1,
                content="测试",
                cron=cron,
                natural_language="测试"
            )
            assert task.id.startswith("task_")
    
    def test_invalid_cron_expression(self, scheduler):
        """测试无效的 Cron 表达式"""
        # 无效的 Cron 表达式应该不会崩溃
        # 但任务可能不会被调度
        task = scheduler.add_task(
            user_id=1,
            content="测试",
            cron="invalid cron",
            natural_language="测试"
        )
        
        # 任务仍会被创建
        assert task.id.startswith("task_")


class TestMultipleUsers:
    """多用户测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def scheduler(self, temp_dir):
        """创建调度器实例"""
        sched = TaskScheduler()
        sched.task_store = TaskStore(tasks_dir=temp_dir)
        return sched
    
    def test_tasks_isolated_by_user(self, scheduler):
        """测试用户任务隔离"""
        # 为用户 1 添加任务
        task1 = scheduler.add_task(
            user_id=1,
            content="用户1的任务",
            cron="0 9 * * *",
            natural_language="用户1的任务"
        )
        
        # 为用户 2 添加任务
        task2 = scheduler.add_task(
            user_id=2,
            content="用户2的任务",
            cron="0 10 * * *",
            natural_language="用户2的任务"
        )
        
        # 验证隔离
        user1_tasks = scheduler.get_user_tasks(1)
        user2_tasks = scheduler.get_user_tasks(2)
        
        assert len(user1_tasks) == 1
        assert len(user2_tasks) == 1
        assert user1_tasks[0].content == "用户1的任务"
        assert user2_tasks[0].content == "用户2的任务"
    
    def test_delete_task_only_affects_own_user(self, scheduler):
        """测试删除任务只影响自己的用户"""
        task1 = scheduler.add_task(
            user_id=1,
            content="用户1的任务",
            cron="0 9 * * *",
            natural_language="用户1的任务"
        )
        
        task2 = scheduler.add_task(
            user_id=2,
            content="用户2的任务",
            cron="0 10 * * *",
            natural_language="用户2的任务"
        )
        
        # 删除用户 1 的任务
        scheduler.remove_task(1, task1.id)
        
        # 验证用户 2 的任务不受影响
        user2_tasks = scheduler.get_user_tasks(2)
        assert len(user2_tasks) == 1
