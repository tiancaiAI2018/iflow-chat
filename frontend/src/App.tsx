import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { useNotifications, NotificationProvider } from './hooks/useNotifications';
import { ChatProvider } from './contexts/ChatContext';
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
  const [isConversationDrawerOpen, setIsConversationDrawerOpen] = useState(false);
  const { addNotification, unreadCount } = useNotifications();

  // 在通知页面时隐藏弹窗
  useEffect(() => {
    if (location.pathname === '/notifications') {
      setShowNotificationPopup(false);
    }
  }, [location.pathname]);

  const toggleNotificationPopup = () => {
    setShowNotificationPopup((prev) => !prev);
  };

  const openConversationDrawer = () => {
    setIsConversationDrawerOpen(true);
  };

  const closeConversationDrawer = () => {
    setIsConversationDrawerOpen(false);
  };

  // 克隆子元素并传递 onNotification 和会话抽屉 props
  const childrenWithProps = React.Children.map(children, (child) => {
    if (React.isValidElement(child)) {
      return React.cloneElement(child as React.ReactElement<{ 
        onNotification?: (notification: { id: string; content: string; read: boolean; created_at: string; task_id?: string | null | undefined }) => void;
        isConversationDrawerOpen?: boolean;
        onOpenConversationDrawer?: () => void;
        onCloseConversationDrawer?: () => void;
      }>, {
        onNotification: (notification: { id: string; content: string; read: boolean; created_at: string; task_id?: string | null | undefined }) => {
          addNotification({
            ...notification,
            task_id: notification.task_id ?? null,
          });
        },
        isConversationDrawerOpen,
        onOpenConversationDrawer: openConversationDrawer,
        onCloseConversationDrawer: closeConversationDrawer,
      });
    }
    return child;
  });

  return (
    <div className="app-layout">
      <Header 
        onToggleNotification={toggleNotificationPopup}
        showNotificationPopup={showNotificationPopup}
        onOpenConversationDrawer={openConversationDrawer}
      />
      <main className="app-main">
        {childrenWithProps}
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

// 受保护的路由内容 - 在 Provider 内部
const ProtectedContent: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { addNotification } = useNotifications();
  
  return (
    <ChatProvider onNotification={addNotification}>
      <AppLayout>{children}</AppLayout>
    </ChatProvider>
  );
};

// 受保护的路由容器
const ProtectedLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <ProtectedRoute>
      <NotificationProvider>
        <ProtectedContent>{children}</ProtectedContent>
      </NotificationProvider>
    </ProtectedRoute>
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
        <Route path="/chat" element={<ProtectedLayout><Chat /></ProtectedLayout>} />
        <Route path="/tasks" element={<ProtectedLayout><TaskManager /></ProtectedLayout>} />
        <Route path="/notifications" element={<ProtectedLayout><NotificationsPage /></ProtectedLayout>} />

        {/* 默认路由 */}
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;