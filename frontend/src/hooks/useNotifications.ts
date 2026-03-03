import { useState, useCallback, useEffect } from 'react';
import { apiService } from '../services/api';
import type { Notification, NotificationsResponse } from '../types';

interface UseNotificationsResult {
  notifications: Notification[];
  unreadCount: number;
  isLoading: boolean;
  error: string | null;
  fetchNotifications: (unreadOnly?: boolean) => Promise<void>;
  markAsRead: (notificationId: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  deleteNotification: (notificationId: string) => Promise<void>;
  clearAll: () => Promise<void>;
  addNotification: (notification: Notification) => void;
}

export function useNotifications(): UseNotificationsResult {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 获取通知列表
  const fetchNotifications = useCallback(async (unreadOnly = false) => {
    setIsLoading(true);
    setError(null);
    try {
      const response: NotificationsResponse = await apiService.getNotifications({
        unread_only: unreadOnly,
        limit: 50,
      });
      setNotifications(response.notifications || []);
      setUnreadCount(response.unread_count || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取通知失败');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 标记单条通知为已读
  const markAsRead = useCallback(async (notificationId: string) => {
    try {
      await apiService.markNotificationAsRead(notificationId);
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notificationId ? { ...n, read: true } : n
        )
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      setError(err instanceof Error ? err.message : '标记已读失败');
    }
  }, []);

  // 标记所有通知为已读
  const markAllAsRead = useCallback(async () => {
    try {
      await apiService.markAllNotificationsAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : '标记全部已读失败');
    }
  }, []);

  // 删除单条通知
  const deleteNotification = useCallback(async (notificationId: string) => {
    try {
      await apiService.deleteNotification(notificationId);
      setNotifications((prev) => {
        const notification = prev.find((n) => n.id === notificationId);
        if (notification && !notification.read) {
          setUnreadCount((c) => Math.max(0, c - 1));
        }
        return prev.filter((n) => n.id !== notificationId);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除通知失败');
    }
  }, []);

  // 清除所有通知
  const clearAll = useCallback(async () => {
    try {
      await apiService.clearAllNotifications();
      setNotifications([]);
      setUnreadCount(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : '清除通知失败');
    }
  }, []);

  // 添加新通知（用于 WebSocket 实时推送）
  const addNotification = useCallback((notification: Notification) => {
    setNotifications((prev) => [notification, ...prev]);
    if (!notification.read) {
      setUnreadCount((prev) => prev + 1);
    }
  }, []);

  // 初始加载
  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  return {
    notifications,
    unreadCount,
    isLoading,
    error,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    clearAll,
    addNotification,
  };
}

export default useNotifications;
