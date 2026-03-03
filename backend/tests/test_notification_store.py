"""
通知存储服务测试
"""
import json
import os
import tempfile
import shutil
from datetime import datetime

import pytest

from backend.services.notification_store import NotificationStore, get_notification_store


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def notification_store(temp_dir):
    """创建通知存储实例"""
    return NotificationStore(notifications_dir=temp_dir)


class TestNotificationStoreInit:
    """测试初始化"""
    
    def test_init_creates_directory(self, temp_dir):
        """测试初始化时创建目录"""
        custom_dir = os.path.join(temp_dir, "custom_notifications")
        assert not os.path.exists(custom_dir)
        
        store = NotificationStore(notifications_dir=custom_dir)
        
        assert os.path.exists(custom_dir)
    
    def test_init_uses_custom_directory(self, temp_dir):
        """测试使用自定义目录"""
        store = NotificationStore(notifications_dir=temp_dir)
        
        assert store.notifications_dir == temp_dir
    
    def test_get_user_file_path(self, notification_store, temp_dir):
        """测试获取用户文件路径"""
        user_id = 123
        
        file_path = notification_store._get_user_file(user_id)
        
        assert file_path == os.path.join(temp_dir, "123.json")


class TestNotificationStoreLoad:
    """测试加载通知"""
    
    def test_load_empty_notifications(self, notification_store):
        """测试加载空通知（用户无通知文件）"""
        user_id = 999
        
        data = notification_store.load_user_notifications(user_id)
        
        assert data["user_id"] == user_id
        assert data["notifications"] == []
    
    def test_load_existing_notifications(self, notification_store, temp_dir):
        """测试加载已存在的通知"""
        user_id = 1
        existing_data = {
            "user_id": user_id,
            "notifications": [
                {
                    "id": "notif_001",
                    "task_id": "task_001",
                    "content": "测试通知",
                    "read": False,
                    "created_at": "2026-03-03T10:00:00"
                }
            ]
        }
        
        # 创建测试文件
        file_path = os.path.join(temp_dir, f"{user_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f)
        
        data = notification_store.load_user_notifications(user_id)
        
        assert data["user_id"] == user_id
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["id"] == "notif_001"
    
    def test_load_corrupted_json(self, notification_store, temp_dir):
        """测试加载损坏的 JSON 文件"""
        user_id = 2
        
        # 创建损坏的 JSON 文件
        file_path = os.path.join(temp_dir, f"{user_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("invalid json content{{{")
        
        data = notification_store.load_user_notifications(user_id)
        
        # 应该返回空数据
        assert data["user_id"] == user_id
        assert data["notifications"] == []


class TestNotificationStoreSave:
    """测试保存通知"""
    
    def test_save_user_notifications(self, notification_store, temp_dir):
        """测试保存用户通知"""
        user_id = 1
        data = {
            "user_id": user_id,
            "notifications": [
                {
                    "id": "notif_001",
                    "task_id": "task_001",
                    "content": "测试通知",
                    "read": False,
                    "created_at": "2026-03-03T10:00:00"
                }
            ]
        }
        
        notification_store.save_user_notifications(user_id, data)
        
        # 验证文件已创建
        file_path = os.path.join(temp_dir, f"{user_id}.json")
        assert os.path.exists(file_path)
        
        # 验证内容
        with open(file_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data["user_id"] == user_id
        assert len(saved_data["notifications"]) == 1
    
    def test_save_preserves_chinese_characters(self, notification_store, temp_dir):
        """测试保存中文内容"""
        user_id = 1
        data = {
            "user_id": user_id,
            "notifications": [
                {
                    "id": "notif_001",
                    "content": "这是一条中文通知内容",
                    "read": False
                }
            ]
        }
        
        notification_store.save_user_notifications(user_id, data)
        
        file_path = os.path.join(temp_dir, f"{user_id}.json")
        with open(file_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data["notifications"][0]["content"] == "这是一条中文通知内容"


class TestNotificationStoreAdd:
    """测试添加通知"""
    
    def test_add_notification(self, notification_store):
        """测试添加通知"""
        user_id = 1
        task_id = "task_001"
        content = "任务执行完成"
        
        notification = notification_store.add_notification(
            user_id=user_id,
            task_id=task_id,
            content=content
        )
        
        assert notification["id"].startswith("notif_")
        assert notification["task_id"] == task_id
        assert notification["content"] == content
        assert notification["read"] is False
        assert "created_at" in notification
    
    def test_add_notification_inserts_at_front(self, notification_store):
        """测试新通知插入到最前面"""
        user_id = 1
        
        # 添加第一个通知
        first = notification_store.add_notification(user_id, "task_001", "第一条")
        
        # 添加第二个通知
        second = notification_store.add_notification(user_id, "task_002", "第二条")
        
        # 验证顺序
        data = notification_store.load_user_notifications(user_id)
        assert data["notifications"][0]["id"] == second["id"]
        assert data["notifications"][1]["id"] == first["id"]
    
    def test_add_notification_limits_count(self, notification_store):
        """测试通知数量限制（最多100条）"""
        user_id = 1
        
        # 添加 105 条通知
        for i in range(105):
            notification_store.add_notification(user_id, f"task_{i}", f"通知 {i}")
        
        data = notification_store.load_user_notifications(user_id)
        
        # 应该只有 100 条
        assert len(data["notifications"]) == 100
        
        # 应该保留最新的（task_105 到 task_6）
        assert data["notifications"][0]["task_id"] == "task_104"
    
    def test_add_notification_data_structure(self, notification_store):
        """测试通知数据结构"""
        user_id = 1
        task_id = "task_001"
        content = "测试内容"
        
        notification = notification_store.add_notification(user_id, task_id, content)
        
        # 验证所有必需字段
        assert "id" in notification
        assert "task_id" in notification
        assert "content" in notification
        assert "read" in notification
        assert "created_at" in notification
        
        # 验证字段类型
        assert isinstance(notification["id"], str)
        assert isinstance(notification["task_id"], str)
        assert isinstance(notification["content"], str)
        assert isinstance(notification["read"], bool)
        assert isinstance(notification["created_at"], str)


class TestNotificationStoreGet:
    """测试获取通知"""
    
    def test_get_notifications(self, notification_store):
        """测试获取通知列表"""
        user_id = 1
        
        # 添加几条通知
        notification_store.add_notification(user_id, "task_001", "通知1")
        notification_store.add_notification(user_id, "task_002", "通知2")
        notification_store.add_notification(user_id, "task_003", "通知3")
        
        result = notification_store.get_notifications(user_id)
        
        assert len(result["notifications"]) == 3
        assert result["total"] == 3
        assert result["unread_count"] == 3
    
    def test_get_notifications_unread_only(self, notification_store):
        """测试只获取未读通知"""
        user_id = 1
        
        # 添加几条通知
        notif1 = notification_store.add_notification(user_id, "task_001", "通知1")
        notif2 = notification_store.add_notification(user_id, "task_002", "通知2")
        
        # 标记第一条为已读
        notification_store.mark_as_read(user_id, notif1["id"])
        
        result = notification_store.get_notifications(user_id, unread_only=True)
        
        assert len(result["notifications"]) == 1
        assert result["notifications"][0]["id"] == notif2["id"]
        assert result["unread_count"] == 1
    
    def test_get_notifications_pagination(self, notification_store):
        """测试分页获取通知"""
        user_id = 1
        
        # 添加 5 条通知
        for i in range(5):
            notification_store.add_notification(user_id, f"task_{i}", f"通知 {i}")
        
        # 获取第一页（每页2条）
        result = notification_store.get_notifications(user_id, limit=2, offset=0)
        
        assert len(result["notifications"]) == 2
        assert result["total"] == 5
        
        # 获取第二页
        result = notification_store.get_notifications(user_id, limit=2, offset=2)
        
        assert len(result["notifications"]) == 2
    
    def test_get_notifications_empty(self, notification_store):
        """测试获取空通知列表"""
        user_id = 999
        
        result = notification_store.get_notifications(user_id)
        
        assert result["notifications"] == []
        assert result["total"] == 0
        assert result["unread_count"] == 0
    
    def test_get_notifications_unread_count_with_read(self, notification_store):
        """测试未读数量计算（包含已读）"""
        user_id = 1
        
        # 添加 3 条通知
        notif1 = notification_store.add_notification(user_id, "task_001", "通知1")
        notif2 = notification_store.add_notification(user_id, "task_002", "通知2")
        notification_store.add_notification(user_id, "task_003", "通知3")
        
        # 标记第一条为已读
        notification_store.mark_as_read(user_id, notif1["id"])
        
        result = notification_store.get_notifications(user_id)
        
        assert result["unread_count"] == 2


class TestNotificationStoreMarkAsRead:
    """测试标记已读"""
    
    def test_mark_as_read(self, notification_store):
        """测试标记通知为已读"""
        user_id = 1
        notification = notification_store.add_notification(user_id, "task_001", "测试通知")
        
        result = notification_store.mark_as_read(user_id, notification["id"])
        
        assert result is True
        
        # 验证状态已更新
        data = notification_store.load_user_notifications(user_id)
        notif = [n for n in data["notifications"] if n["id"] == notification["id"]][0]
        assert notif["read"] is True
    
    def test_mark_as_read_nonexistent_notification(self, notification_store):
        """测试标记不存在的通知"""
        user_id = 1
        
        result = notification_store.mark_as_read(user_id, "notif_nonexistent")
        
        assert result is False
    
    def test_mark_as_read_wrong_user(self, notification_store):
        """测试标记其他用户的通知"""
        user_id_1 = 1
        user_id_2 = 2
        
        notification = notification_store.add_notification(user_id_1, "task_001", "用户1的通知")
        
        # 用户2尝试标记用户1的通知
        result = notification_store.mark_as_read(user_id_2, notification["id"])
        
        assert result is False
        
        # 验证用户1的通知仍然是未读
        data = notification_store.load_user_notifications(user_id_1)
        assert data["notifications"][0]["read"] is False


class TestNotificationStoreDelete:
    """测试删除通知"""
    
    def test_delete_notification(self, notification_store):
        """测试删除通知"""
        user_id = 1
        notification = notification_store.add_notification(user_id, "task_001", "测试通知")
        
        result = notification_store.delete_notification(user_id, notification["id"])
        
        assert result is True
        
        # 验证已删除
        data = notification_store.load_user_notifications(user_id)
        assert len(data["notifications"]) == 0
    
    def test_delete_notification_nonexistent(self, notification_store):
        """测试删除不存在的通知"""
        user_id = 1
        
        result = notification_store.delete_notification(user_id, "notif_nonexistent")
        
        assert result is False
    
    def test_delete_notification_wrong_user(self, notification_store):
        """测试删除其他用户的通知"""
        user_id_1 = 1
        user_id_2 = 2
        
        notification = notification_store.add_notification(user_id_1, "task_001", "用户1的通知")
        
        # 用户2尝试删除用户1的通知
        result = notification_store.delete_notification(user_id_2, notification["id"])
        
        assert result is False
        
        # 验证用户1的通知仍然存在
        data = notification_store.load_user_notifications(user_id_1)
        assert len(data["notifications"]) == 1


class TestNotificationStoreMarkAllAsRead:
    """测试标记全部已读"""
    
    def test_mark_all_as_read(self, notification_store):
        """测试标记所有通知为已读"""
        user_id = 1
        
        # 添加 3 条通知
        notification_store.add_notification(user_id, "task_001", "通知1")
        notification_store.add_notification(user_id, "task_002", "通知2")
        notification_store.add_notification(user_id, "task_003", "通知3")
        
        count = notification_store.mark_all_as_read(user_id)
        
        assert count == 3
        
        # 验证所有都是已读
        data = notification_store.load_user_notifications(user_id)
        for notif in data["notifications"]:
            assert notif["read"] is True
    
    def test_mark_all_as_read_with_some_read(self, notification_store):
        """测试部分已读时标记全部已读"""
        user_id = 1
        
        # 添加 3 条通知
        notif1 = notification_store.add_notification(user_id, "task_001", "通知1")
        notification_store.add_notification(user_id, "task_002", "通知2")
        notification_store.add_notification(user_id, "task_003", "通知3")
        
        # 先标记第一条为已读
        notification_store.mark_as_read(user_id, notif1["id"])
        
        count = notification_store.mark_all_as_read(user_id)
        
        # 应该只标记了 2 条
        assert count == 2
    
    def test_mark_all_as_read_empty(self, notification_store):
        """测试空通知时标记全部已读"""
        user_id = 999
        
        count = notification_store.mark_all_as_read(user_id)
        
        assert count == 0


class TestNotificationStoreClearAll:
    """测试清除所有通知"""
    
    def test_clear_all(self, notification_store):
        """测试清除所有通知"""
        user_id = 1
        
        # 添加 3 条通知
        notification_store.add_notification(user_id, "task_001", "通知1")
        notification_store.add_notification(user_id, "task_002", "通知2")
        notification_store.add_notification(user_id, "task_003", "通知3")
        
        count = notification_store.clear_all(user_id)
        
        assert count == 3
        
        # 验证已清空
        data = notification_store.load_user_notifications(user_id)
        assert len(data["notifications"]) == 0
    
    def test_clear_all_empty(self, notification_store):
        """测试空通知时清除"""
        user_id = 999
        
        count = notification_store.clear_all(user_id)
        
        assert count == 0


class TestGetNotificationStoreSingleton:
    """测试单例模式"""
    
    def test_get_notification_store_singleton(self):
        """测试获取通知存储单例"""
        from backend.services.notification_store import _notification_store
        
        # 重置全局实例
        import backend.services.notification_store as module
        module._notification_store = None
        
        store1 = get_notification_store()
        store2 = get_notification_store()
        
        assert store1 is store2
    
    def test_get_notification_store_returns_notification_store(self):
        """测试单例返回正确的类型"""
        from backend.services.notification_store import _notification_store
        import backend.services.notification_store as module
        module._notification_store = None
        
        store = get_notification_store()
        
        assert isinstance(store, NotificationStore)


class TestNotificationStoreIntegration:
    """集成测试"""
    
    def test_full_workflow(self, notification_store):
        """测试完整工作流程"""
        user_id = 1
        
        # 1. 添加通知
        notif1 = notification_store.add_notification(user_id, "task_001", "任务1完成")
        notif2 = notification_store.add_notification(user_id, "task_002", "任务2完成")
        
        # 2. 获取通知列表
        result = notification_store.get_notifications(user_id)
        assert result["total"] == 2
        assert result["unread_count"] == 2
        
        # 3. 标记一条为已读
        notification_store.mark_as_read(user_id, notif1["id"])
        
        # 4. 再次获取，验证未读数量
        result = notification_store.get_notifications(user_id)
        assert result["unread_count"] == 1
        
        # 5. 只获取未读
        result = notification_store.get_notifications(user_id, unread_only=True)
        assert len(result["notifications"]) == 1
        
        # 6. 删除一条
        notification_store.delete_notification(user_id, notif2["id"])
        
        # 7. 最终验证
        result = notification_store.get_notifications(user_id)
        assert result["total"] == 1
    
    def test_multiple_users(self, notification_store):
        """测试多用户隔离"""
        user_id_1 = 1
        user_id_2 = 2
        
        # 用户1添加通知
        notif1 = notification_store.add_notification(user_id_1, "task_001", "用户1的通知")
        
        # 用户2添加通知
        notif2 = notification_store.add_notification(user_id_2, "task_002", "用户2的通知")
        
        # 验证用户1只能看到自己的通知
        result1 = notification_store.get_notifications(user_id_1)
        assert result1["total"] == 1
        assert result1["notifications"][0]["content"] == "用户1的通知"
        
        # 验证用户2只能看到自己的通知
        result2 = notification_store.get_notifications(user_id_2)
        assert result2["total"] == 1
        assert result2["notifications"][0]["content"] == "用户2的通知"
        
        # 用户1标记已读不应影响用户2
        notification_store.mark_as_read(user_id_1, notif1["id"])
        
        result2 = notification_store.get_notifications(user_id_2)
        assert result2["unread_count"] == 1
