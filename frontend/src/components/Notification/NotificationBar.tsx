import React, { useState } from 'react';
import { useNotifications } from '../../hooks/useNotifications';
import { NotificationItem } from './NotificationItem';
import './Notification.css';

interface NotificationBarProps {
  onClose?: () => void;
}

export const NotificationBar: React.FC<NotificationBarProps> = ({ onClose }) => {
  const {
    notifications,
    unreadCount,
    isLoading,
    error,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    clearAll,
  } = useNotifications();

  const [filter, setFilter] = useState<'all' | 'unread'>('all');

  const filteredNotifications = filter === 'unread'
    ? notifications.filter((n) => !n.read)
    : notifications;

  const handleMarkAllRead = async () => {
    if (unreadCount > 0) {
      await markAllAsRead();
    }
  };

  const handleClearAll = async () => {
    if (notifications.length > 0 && window.confirm('确定要清除所有通知吗？')) {
      await clearAll();
    }
  };

  return (
    <div className="notification-bar">
      <div className="notification-header">
        <h3 className="notification-title">
          通知
          {unreadCount > 0 && (
            <span className="notification-badge">{unreadCount}</span>
          )}
        </h3>
        <button className="notification-close-btn" onClick={onClose}>
          ×
        </button>
      </div>

      <div className="notification-controls">
        <div className="notification-filters">
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            全部
          </button>
          <button
            className={`filter-btn ${filter === 'unread' ? 'active' : ''}`}
            onClick={() => setFilter('unread')}
          >
            未读 ({unreadCount})
          </button>
        </div>
        <div className="notification-actions-bar">
          <button
            className="action-btn"
            onClick={handleMarkAllRead}
            disabled={unreadCount === 0}
          >
            全部已读
          </button>
          <button
            className="action-btn danger"
            onClick={handleClearAll}
            disabled={notifications.length === 0}
          >
            清空
          </button>
        </div>
      </div>

      <div className="notification-list">
        {isLoading && (
          <div className="notification-loading">加载中...</div>
        )}

        {error && (
          <div className="notification-error">{error}</div>
        )}

        {!isLoading && !error && filteredNotifications.length === 0 && (
          <div className="notification-empty">
            {filter === 'unread' ? '没有未读通知' : '暂无通知'}
          </div>
        )}

        {!isLoading && !error && filteredNotifications.length > 0 && (
          filteredNotifications.map((notification) => (
            <NotificationItem
              key={notification.id}
              notification={notification}
              onMarkRead={markAsRead}
              onDelete={deleteNotification}
            />
          ))
        )}
      </div>
    </div>
  );
};

export default NotificationBar;
