import React from 'react';
import type { Notification } from '../../types';
import './Notification.css';

interface NotificationItemProps {
  notification: Notification;
  onMarkRead: (id: string) => void;
  onDelete: (id: string) => void;
}

export const NotificationItem: React.FC<NotificationItemProps> = ({
  notification,
  onMarkRead,
  onDelete,
}) => {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes} 分钟前`;
    if (hours < 24) return `${hours} 小时前`;
    if (days < 7) return `${days} 天前`;
    return date.toLocaleDateString('zh-CN');
  };

  return (
    <div className={`notification-item ${notification.read ? 'read' : 'unread'}`}>
      <div className="notification-indicator">
        {!notification.read && <span className="unread-dot"></span>}
      </div>
      <div className="notification-content">
        <div className="notification-text">{notification.content}</div>
        <div className="notification-meta">
          <span className="notification-time">{formatDate(notification.created_at)}</span>
          {notification.task_id && (
            <span className="notification-task">定时任务</span>
          )}
        </div>
      </div>
      <div className="notification-actions">
        {!notification.read && (
          <button
            className="notification-btn mark-read-btn"
            onClick={() => onMarkRead(notification.id)}
            title="标记已读"
          >
            ✓
          </button>
        )}
        <button
          className="notification-btn delete-btn"
          onClick={() => onDelete(notification.id)}
          title="删除"
        >
          ×
        </button>
      </div>
    </div>
  );
};

export default NotificationItem;
