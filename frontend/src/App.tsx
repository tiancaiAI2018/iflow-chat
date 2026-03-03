import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { useNotifications } from './hooks/useNotifications';
import { Login, Register, LoginEmail } from './components/Auth';
import { Chat } from './components/Chat';
import { TaskManager } from './components/TaskManager';
import { NotificationBar } from './components/Notification';
import { Header } from './components/Layout';
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
  const location = useLocation();
  const [showNotificationPopup, setShowNotificationPopup] = useState(false);

  // 在通知页面时隐藏弹窗
  useEffect(() => {
    if (location.pathname === '/notifications') {
      setShowNotificationPopup(false);
    }
  }, [location.pathname]);

  const toggleNotificationPopup = () => {
    setShowNotificationPopup((prev) => !prev);
  };

  return (
    <div className="app-layout">
      <Header 
        onToggleNotification={toggleNotificationPopup}
        showNotificationPopup={showNotificationPopup}
      />
      <main className="app-main">
        {children}
        {showNotificationPopup && location.pathname !== '/notifications' && (
          <div className="notification-popup" onClick={() => setShowNotificationPopup(false)}>
            <div onClick={(e) => e.stopPropagation()}>
              <NotificationBar onClose={() => setShowNotificationPopup(false)} />
            </div>
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
