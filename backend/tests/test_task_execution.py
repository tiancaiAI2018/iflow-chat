"""
任务执行服务测试
"""
import pytest
import asyncio
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.task_executor import (
    NotificationStore,
    TaskExecutor,
    get_notification_store,
    get_task_executor,
    execute_task_callback,
)


class TestNotificationStore:
    """NotificationStore 通知存储测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def notification_store(self, temp_dir):
        """创建通知存储实例"""
        return NotificationStore(notifications_dir=temp_dir)
    
    def test_ensure_dir_created(self, notification_store, temp_dir):
        """测试目录创建"""
        assert os.path.exists(temp_dir)
    
    def test_get_user_file_path(self, notification_store, temp_dir):
        """测试用户文件路径"""
        path = notification_store._get_user_file(1)
        assert path == os.path.join(temp_dir, "1.json")
    
    def test_load_empty_notifications(self, notification_store):
        """测试加载空通知列表"""
        data = notification_store.load_user_notifications(1)
        assert data == {"user_id": 1, "notifications": []}
    
    def test_add_notification(self, notification_store):
        """测试添加通知"""
        notification = notification_store.add_notification(
            user_id=1,
            task_id="task_001",
            content="测试通知内容"
        )
        
        assert notification["id"].startswith("notif_")
        assert notification["task_id"] == "task_001"
        assert notification["content"] == "测试通知内容"
        assert notification["read"] is False
        assert "created_at" in notification
    
    def test_add_notification_saves_to_file(self, notification_store, temp_dir):
        """测试添加通知保存到文件"""
        notification_store.add_notification(
            user_id=1,
            task_id="task_001",
            content="测试通知内容"
        )
        
        # 验证文件已创建
        file_path = os.path.join(temp_dir, "1.json")
        assert os.path.exists(file_path)
        
        # 验证文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data["user_id"] == 1
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["task_id"] == "task_001"
    
    def test_add_multiple_notifications(self, notification_store):
        """测试添加多个通知"""
        notification_store.add_notification(
            user_id=1,
            task_id="task_001",
            content="通知1"
        )
        
        notification_store.add_notification(
            user_id=1,
            task_id="task_002",
            content="通知2"
        )
        
        data = notification_store.load_user_notifications(1)
        assert len(data["notifications"]) == 2
        
        # 新通知应该在前
        assert data["notifications"][0]["content"] == "通知2"
        assert data["notifications"][1]["content"] == "通知1"
    
    def test_notification_limit(self, notification_store):
        """测试通知数量限制"""
        # 添加 150 条通知
        for i in range(150):
            notification_store.add_notification(
                user_id=1,
                task_id=f"task_{i}",
                content=f"通知_{i}"
            )
        
        data = notification_store.load_user_notifications(1)
        assert len(data["notifications"]) == 100  # 限制 100 条
    
    def test_get_notifications(self, notification_store):
        """测试获取通知列表"""
        # 添加一些通知
        notification_store.add_notification(user_id=1, task_id="task_001", content="通知1")
        notification_store.add_notification(user_id=1, task_id="task_002", content="通知2")
        notification_store.add_notification(user_id=1, task_id="task_003", content="通知3")
        
        result = notification_store.get_notifications(user_id=1)
        
        assert len(result["notifications"]) == 3
        assert result["total"] == 3
        assert result["unread_count"] == 3
    
    def test_get_notifications_with_pagination(self, notification_store):
        """测试分页获取通知"""
        # 添加 10 条通知
        for i in range(10):
            notification_store.add_notification(user_id=1, task_id=f"task_{i}", content=f"通知_{i}")
        
        # 获取第一页
        result = notification_store.get_notifications(user_id=1, limit=5, offset=0)
        assert len(result["notifications"]) == 5
        
        # 获取第二页
        result = notification_store.get_notifications(user_id=1, limit=5, offset=5)
        assert len(result["notifications"]) == 5
    
    def test_get_unread_only_notifications(self, notification_store):
        """测试只获取未读通知"""
        notification_store.add_notification(user_id=1, task_id="task_001", content="通知1")
        notification_store.add_notification(user_id=1, task_id="task_002", content="通知2")
        
        # 标记第一个为已读
        notification_store.mark_as_read(1, notification_store.load_user_notifications(1)["notifications"][1]["id"])
        
        result = notification_store.get_notifications(user_id=1, unread_only=True)
        
        assert len(result["notifications"]) == 1
        assert result["unread_count"] == 1
    
    def test_mark_as_read(self, notification_store):
        """测试标记已读"""
        notification = notification_store.add_notification(
            user_id=1,
            task_id="task_001",
            content="测试通知"
        )
        
        result = notification_store.mark_as_read(1, notification["id"])
        assert result is True
        
        # 验证已标记
        data = notification_store.load_user_notifications(1)
        assert data["notifications"][0]["read"] is True
    
    def test_mark_nonexistent_as_read(self, notification_store):
        """测试标记不存在的通知为已读"""
        result = notification_store.mark_as_read(1, "notif_999")
        assert result is False
    
    def test_delete_notification(self, notification_store):
        """测试删除通知"""
        notification = notification_store.add_notification(
            user_id=1,
            task_id="task_001",
            content="测试通知"
        )
        
        result = notification_store.delete_notification(1, notification["id"])
        assert result is True
        
        # 验证已删除
        data = notification_store.load_user_notifications(1)
        assert len(data["notifications"]) == 0
    
    def test_delete_nonexistent_notification(self, notification_store):
        """测试删除不存在的通知"""
        result = notification_store.delete_notification(1, "notif_999")
        assert result is False
    
    def test_load_corrupted_json(self, notification_store, temp_dir):
        """测试加载损坏的 JSON 文件"""
        # 创建损坏的 JSON 文件
        file_path = os.path.join(temp_dir, "1.json")
        with open(file_path, 'w') as f:
            f.write("invalid json {")
        
        # 应该返回空数据
        data = notification_store.load_user_notifications(1)
        assert data == {"user_id": 1, "notifications": []}


class TestTaskExecutor:
    """TaskExecutor 任务执行器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def notification_store(self, temp_dir):
        """创建通知存储实例"""
        return NotificationStore(notifications_dir=temp_dir)
    
    @pytest.fixture
    def mock_websocket_manager(self):
        """创建模拟 WebSocket 管理器"""
        manager = MagicMock()
        manager.is_user_online = MagicMock(return_value=False)
        manager.send_to_user = AsyncMock(return_value=1)
        return manager
    
    @pytest.fixture
    def executor(self, notification_store, mock_websocket_manager):
        """创建任务执行器实例"""
        return TaskExecutor(
            notification_store=notification_store,
            websocket_manager=mock_websocket_manager,
        )
    
    @pytest.mark.asyncio
    async def test_execute_task_success(self, executor, notification_store):
        """测试成功执行任务"""
        # 模拟 iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "这是 iFlow 的响应"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        assert result["success"] is True
        assert result["task_id"] == "task_001"
        assert result["response"] == "这是 iFlow 的响应"
        assert result["error"] is None
        assert result["notification"] is not None
    
    @pytest.mark.asyncio
    async def test_execute_task_saves_notification(self, executor, notification_store):
        """测试执行任务保存通知"""
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "响应内容"
            
            await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        # 验证通知已保存
        notifications = notification_store.get_notifications(user_id=1)
        assert len(notifications["notifications"]) == 1
        # 通知内容包含任务内容和响应
        notification_content = notifications["notifications"][0]["content"]
        assert "查看股票" in notification_content
        assert "响应内容" in notification_content
    
    @pytest.mark.asyncio
    async def test_execute_task_pushes_to_online_user(self, executor, mock_websocket_manager, notification_store):
        """测试在线用户收到推送"""
        # 设置用户在线
        mock_websocket_manager.is_user_online.return_value = True
        
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "响应"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        # 验证推送被调用
        mock_websocket_manager.send_to_user.assert_called_once()
        assert result["pushed"] is True
    
    @pytest.mark.asyncio
    async def test_execute_task_no_push_for_offline_user(self, executor, mock_websocket_manager):
        """测试离线用户不收到推送"""
        # 设置用户离线
        mock_websocket_manager.is_user_online.return_value = False
        
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "响应"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        # 验证推送未被调用
        mock_websocket_manager.send_to_user.assert_not_called()
        assert result["pushed"] is False
    
    @pytest.mark.asyncio
    async def test_execute_task_handles_iflow_error(self, executor, notification_store):
        """测试处理 iFlow 错误"""
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.side_effect = Exception("iFlow 连接失败")
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        assert result["success"] is False
        assert "iFlow 连接失败" in result["error"]
        
        # 即使失败，也应该保存失败通知
        assert result["notification"] is not None
        assert "执行失败" in result["notification"]["content"]
    
    @pytest.mark.asyncio
    async def test_execute_task_handles_push_error(self, executor, mock_websocket_manager):
        """测试处理推送错误"""
        mock_websocket_manager.is_user_online.return_value = True
        mock_websocket_manager.send_to_user.side_effect = Exception("推送失败")
        
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "响应"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        # 任务应该成功执行，只是推送失败
        assert result["success"] is True
        assert result["pushed"] is False
    
    def test_build_notification_content(self, executor):
        """测试构建通知内容"""
        content = executor._build_notification_content(
            task_id="task_001",
            task_content="查看股票",
            response="今日上证指数 3000 点"
        )
        
        assert "定时任务执行结果" in content
        assert "查看股票" in content
        assert "今日上证指数 3000 点" in content


class TestCallIFlow:
    """iFlow 调用测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def executor(self, temp_dir):
        """创建任务执行器实例"""
        notification_store = NotificationStore(notifications_dir=temp_dir)
        return TaskExecutor(notification_store=notification_store)
    
    @pytest.mark.asyncio
    async def test_call_iflow_returns_response(self, executor):
        """测试调用 iFlow 返回响应"""
        # 模拟 IFlowClientService
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        # 模拟 query_stream 返回
        from backend.services.iflow_client import ChatMessage, MessageType
        
        async def mock_stream(message):
            yield ChatMessage(type=MessageType.TEXT, content="Hello", is_delta=True)
            yield ChatMessage(type=MessageType.TEXT, content=" World", is_delta=True)
            yield ChatMessage(type=MessageType.TASK_FINISH, is_finished=True)
        
        mock_client.query_stream = mock_stream
        
        with patch('backend.services.task_executor.IFlowClientService', return_value=mock_client):
            response = await executor._call_iflow("测试消息")
        
        assert response == "Hello World"
    
    @pytest.mark.asyncio
    async def test_call_iflow_handles_error(self, executor):
        """测试调用 iFlow 处理错误"""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        from backend.services.iflow_client import ChatMessage, MessageType
        
        async def mock_stream(message):
            yield ChatMessage(type=MessageType.ERROR, content="连接超时")
        
        mock_client.query_stream = mock_stream
        
        with patch('backend.services.task_executor.IFlowClientService', return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                await executor._call_iflow("测试消息")
            
            assert "iFlow error" in str(exc_info.value)


class TestPushNotification:
    """通知推送测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def executor(self, temp_dir):
        """创建任务执行器实例"""
        notification_store = NotificationStore(notifications_dir=temp_dir)
        return TaskExecutor(notification_store=notification_store)
    
    @pytest.mark.asyncio
    async def test_push_notification_success(self, executor):
        """测试成功推送通知"""
        mock_manager = AsyncMock()
        mock_manager.send_to_user = AsyncMock(return_value=2)  # 2 个连接
        
        executor.websocket_manager = mock_manager
        
        notification = {"id": "notif_001", "content": "测试"}
        result = await executor._push_notification(1, notification)
        
        assert result is True
        mock_manager.send_to_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_push_notification_no_connections(self, executor):
        """测试推送通知但无连接"""
        mock_manager = AsyncMock()
        mock_manager.send_to_user = AsyncMock(return_value=0)  # 无连接
        
        executor.websocket_manager = mock_manager
        
        notification = {"id": "notif_001", "content": "测试"}
        result = await executor._push_notification(1, notification)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_push_notification_handles_exception(self, executor):
        """测试推送通知处理异常"""
        mock_manager = AsyncMock()
        mock_manager.send_to_user = AsyncMock(side_effect=Exception("推送失败"))
        
        executor.websocket_manager = mock_manager
        
        notification = {"id": "notif_001", "content": "测试"}
        result = await executor._push_notification(1, notification)
        
        assert result is False


class TestGlobalInstances:
    """全局实例测试"""
    
    def test_get_notification_store_singleton(self):
        """测试获取通知存储单例"""
        # 清除之前的状态
        import backend.services.task_executor as executor_module
        executor_module._notification_store = None
        
        store1 = get_notification_store()
        store2 = get_notification_store()
        
        assert store1 is store2
    
    def test_get_task_executor_singleton(self):
        """测试获取任务执行器单例"""
        # 清除之前的状态
        import backend.services.task_executor as executor_module
        executor_module._task_executor = None
        executor_module._notification_store = None
        
        executor1 = get_task_executor()
        executor2 = get_task_executor()
        
        assert executor1 is executor2
    
    @pytest.mark.asyncio
    async def test_execute_task_callback(self):
        """测试任务执行回调函数"""
        # 清除之前的状态
        import backend.services.task_executor as executor_module
        executor_module._task_executor = None
        executor_module._notification_store = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建使用临时目录的执行器
            notification_store = NotificationStore(notifications_dir=temp_dir)
            executor = TaskExecutor(notification_store=notification_store)
            
            # 设置全局执行器
            executor_module._task_executor = executor
            executor_module._notification_store = notification_store
            
            # 模拟 iFlow
            with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
                mock_iflow.return_value = "响应内容"
                
                await execute_task_callback(
                    user_id=1,
                    task_id="task_001",
                    content="查看股票"
                )
            
            # 验证通知已保存
            notifications = notification_store.get_notifications(user_id=1)
            assert len(notifications["notifications"]) == 1


class TestIntegration:
    """集成测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.mark.asyncio
    async def test_full_task_execution_flow(self, temp_dir):
        """测试完整的任务执行流程"""
        # 创建组件
        notification_store = NotificationStore(notifications_dir=temp_dir)
        mock_ws_manager = MagicMock()
        mock_ws_manager.is_user_online.return_value = True
        mock_ws_manager.send_to_user = AsyncMock(return_value=1)
        
        executor = TaskExecutor(
            notification_store=notification_store,
            websocket_manager=mock_ws_manager,
        )
        
        # 模拟 iFlow 响应
        with patch.object(executor, '_call_iflow', new_callable=AsyncMock) as mock_iflow:
            mock_iflow.return_value = "今日股票表现良好"
            
            result = await executor.execute_task(
                user_id=1,
                task_id="task_001",
                content="查看股票"
            )
        
        # 验证结果
        assert result["success"] is True
        assert result["notification"] is not None
        assert result["pushed"] is True
        
        # 验证通知存储
        notifications = notification_store.get_notifications(user_id=1)
        assert len(notifications["notifications"]) == 1
        assert notifications["unread_count"] == 1
        
        # 验证 WebSocket 推送
        mock_ws_manager.send_to_user.assert_called_once()
        call_args = mock_ws_manager.send_to_user.call_args
        assert call_args[0][0] == 1  # user_id
        message = call_args[0][1]
        assert message["type"] == "notification"
        assert "notification" in message
