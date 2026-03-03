import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { useNotifications } from './hooks/useNotifications';
import { Login, Register, LoginEmail } from './components/Auth';
import { Chat } from './components/Chat';
import { TaskManager } from './components/TaskManager';
import { NotificationBar } from './components/Notification';
import './App.css';

// 通知页面组件
const NotificationsPage: React.FC = () => {
  return (
    <div className="notifications-page">
      <NotificationBar />
    </div>
  );
};

// 受保护路由组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div className="loading">加载中...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// 主应用布局
const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, logout } = useAuth();
  const { unreadCount, fetchNotifications, addNotification } = useNotifications();
  const [showNotificationBar, setShowNotificationBar] = useState(false);
  const location = useLocation();

  // 定期刷新未读数量
  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(() => {
      fetchNotifications();
    }, 60000); // 每分钟刷新一次
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // 在通知页面时隐藏弹窗
  useEffect(() => {
    if (location.pathname === '/notifications') {
      setShowNotificationBar(false);
    }
  }, [location.pathname]);

  const toggleNotificationBar = () => {
    setShowNotificationBar((prev) => !prev);
  };

  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="header-logo">iFlow Chat</div>
        <nav className="header-nav">
          <a href="/chat" className={location.pathname === '/chat' ? 'active' : ''}>对话</a>
          <a href="/tasks" className={location.pathname === '/tasks' ? 'active' : ''}>任务</a>
          <button 
            className="notification-nav-btn"
            onClick={toggleNotificationBar}
          >
            通知
            {unreadCount > 0 && (
              <span className="notification-unread-badge">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>
        </nav>
        <div className="header-user">
          {user && <span>{user.username}</span>}
          <button onClick={logout} className="logout-btn">退出</button>
        </div>
      </header>
      <main className="app-main">
        {children}
        {showNotificationBar && location.pathname !== '/notifications' && (
          <div className="notification-popup">
            <NotificationBar onClose={() => setShowNotificationBar(false)} />
          </div>
        )}
      </main>
    </div>
  );
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 公开路由 */}
        <Route path="/login" element={<Login />} />
        <Route path="/login-email" element={<LoginEmail />} />
        <Route path="/register" element={<Register />} />

        {/* 受保护路由 */}
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <AppLayout><Chat /></AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/tasks"
          element={
            <ProtectedRoute>
              <AppLayout><TaskManager /></AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/notifications"
          element={
            <ProtectedRoute>
              <AppLayout><NotificationsPage /></AppLayout>
            </ProtectedRoute>
          }
        />

        {/* 默认路由 */}
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;