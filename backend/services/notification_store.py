"""
通知存储服务
按用户 ID 存储通知到 JSON 文件
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from backend.config import settings

logger = logging.getLogger(__name__)


class NotificationStore:
    """通知存储管理 - JSON 文件存储"""
    
    def __init__(self, notifications_dir: str = None):
        """
        初始化通知存储
        
        Args:
            notifications_dir: 通知存储目录，默认使用配置中的目录
        """
        self.notifications_dir = notifications_dir or settings.NOTIFICATIONS_DIR
        self._ensure_dir()
    
    def _ensure_dir(self):
        """确保目录存在"""
        os.makedirs(self.notifications_dir, exist_ok=True)
    
    def _get_user_file(self, user_id: int) -> str:
        """
        获取用户通知文件路径
        
        Args:
            user_id: 用户 ID
        
        Returns:
            str: 用户通知文件路径
        """
        return os.path.join(self.notifications_dir, f"{user_id}.json")
    
    def load_user_notifications(self, user_id: int) -> Dict[str, Any]:
        """
        加载用户通知数据
        
        Args:
            user_id: 用户 ID
        
        Returns:
            Dict: 用户通知数据，格式为 {"user_id": int, "notifications": list}
        """
        file_path = self._get_user_file(user_id)
        
        if not os.path.exists(file_path):
            return {"user_id": user_id, "notifications": []}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            return {"user_id": user_id, "notifications": []}
    
    def save_user_notifications(self, user_id: int, data: Dict[str, Any]):
        """
        保存用户通知数据
        
        Args:
            user_id: 用户 ID
            data: 通知数据
        """
        file_path = self._get_user_file(user_id)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_notification(
        self,
        user_id: int,
        task_id: str,
        content: str,
    ) -> Dict[str, Any]:
        """
        添加通知
        
        数据结构:
        {
            "id": "notif_xxx",
            "task_id": "task_xxx",
            "content": "通知内容",
            "read": false,
            "created_at": "2026-03-03T10:00:00"
        }
        
        Args:
            user_id: 用户 ID
            task_id: 关联的任务 ID
            content: 通知内容
        
        Returns:
            Dict: 创建的通知对象
        """
        notification_id = f"notif_{uuid.uuid4().hex[:12]}"
        notification = {
            "id": notification_id,
            "task_id": task_id,
            "content": content,
            "read": False,
            "created_at": datetime.now().isoformat(),
        }
        
        data = self.load_user_notifications(user_id)
        data["notifications"].insert(0, notification)  # 新通知放在最前面
        
        # 限制通知数量，最多保留 100 条
        if len(data["notifications"]) > 100:
            data["notifications"] = data["notifications"][:100]
        
        self.save_user_notifications(user_id, data)
        
        logger.info(f"Notification saved: user_id={user_id}, task_id={task_id}, notif_id={notification_id}")
        
        return notification
    
    def get_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        获取通知列表
        
        Args:
            user_id: 用户 ID
            unread_only: 是否只获取未读
            limit: 限制数量
            offset: 偏移量
        
        Returns:
            Dict: 包含 notifications、unread_count、total 的字典
        """
        data = self.load_user_notifications(user_id)
        notifications = data.get("notifications", [])
        
        if unread_only:
            notifications = [n for n in notifications if not n.get("read", False)]
        
        # 计算未读数量
        all_notifications = data.get("notifications", [])
        unread_count = sum(1 for n in all_notifications if not n.get("read", False))
        
        # 分页
        paginated = notifications[offset:offset + limit]
        
        return {
            "notifications": paginated,
            "unread_count": unread_count,
            "total": len(notifications),
        }
    
    def mark_as_read(self, user_id: int, notification_id: str) -> bool:
        """
        标记通知为已读
        
        Args:
            user_id: 用户 ID
            notification_id: 通知 ID
        
        Returns:
            bool: 是否成功
        """
        data = self.load_user_notifications(user_id)
        
        for notification in data.get("notifications", []):
            if notification.get("id") == notification_id:
                notification["read"] = True
                self.save_user_notifications(user_id, data)
                logger.info(f"Notification marked as read: user_id={user_id}, notif_id={notification_id}")
                return True
        
        return False
    
    def delete_notification(self, user_id: int, notification_id: str) -> bool:
        """
        删除通知
        
        Args:
            user_id: 用户 ID
            notification_id: 通知 ID
        
        Returns:
            bool: 是否成功
        """
        data = self.load_user_notifications(user_id)
        notifications = data.get("notifications", [])
        
        for i, notification in enumerate(notifications):
            if notification.get("id") == notification_id:
                notifications.pop(i)
                self.save_user_notifications(user_id, data)
                logger.info(f"Notification deleted: user_id={user_id}, notif_id={notification_id}")
                return True
        
        return False
    
    def mark_all_as_read(self, user_id: int) -> int:
        """
        标记所有通知为已读
        
        Args:
            user_id: 用户 ID
        
        Returns:
            int: 标记为已读的数量
        """
        data = self.load_user_notifications(user_id)
        count = 0
        
        for notification in data.get("notifications", []):
            if not notification.get("read", False):
                notification["read"] = True
                count += 1
        
        if count > 0:
            self.save_user_notifications(user_id, data)
            logger.info(f"All notifications marked as read: user_id={user_id}, count={count}")
        
        return count
    
    def clear_all(self, user_id: int) -> int:
        """
        清除用户所有通知
        
        Args:
            user_id: 用户 ID
        
        Returns:
            int: 删除的通知数量
        """
        data = self.load_user_notifications(user_id)
        count = len(data.get("notifications", []))
        
        data["notifications"] = []
        self.save_user_notifications(user_id, data)
        
        logger.info(f"All notifications cleared: user_id={user_id}, count={count}")
        
        return count


# 全局通知存储实例
_notification_store: Optional[NotificationStore] = None


def get_notification_store() -> NotificationStore:
    """获取通知存储单例"""
    global _notification_store
    if _notification_store is None:
        _notification_store = NotificationStore()
    return _notification_store
