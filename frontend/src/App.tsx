import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import './App.css';

// 临时占位组件（后续功能开发时替换）
const LoginPage: React.FC = () => <div className="page-placeholder">登录页面 (开发中)</div>;
const RegisterPage: React.FC = () => <div className="page-placeholder">注册页面 (开发中)</div>;
const ChatPage: React.FC = () => <div className="page-placeholder">对话页面 (开发中)</div>;
const TasksPage: React.FC = () => <div className="page-placeholder">任务管理页面 (开发中)</div>;
const NotificationsPage: React.FC = () => <div className="page-placeholder">通知页面 (开发中)</div>;

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

  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="header-logo">iFlow Chat</div>
        <nav className="header-nav">
          <a href="/chat">对话</a>
          <a href="/tasks">任务</a>
          <a href="/notifications">通知</a>
        </nav>
        <div className="header-user">
          {user && <span>{user.username}</span>}
          <button onClick={logout} className="logout-btn">退出</button>
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 公开路由 */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* 受保护路由 */}
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <AppLayout><ChatPage /></AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/tasks"
          element={
            <ProtectedRoute>
              <AppLayout><TasksPage /></AppLayout>
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