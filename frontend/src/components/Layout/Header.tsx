import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useNotifications } from '../../hooks/useNotifications';
import { NotificationBar } from '../Notification';
import NewChatButton from '../Chat/NewChatButton';
import HistoryButton from '../Chat/HistoryButton';
import './Layout.css';

interface HeaderProps {
  onToggleNotification?: () => void;
  showNotificationPopup?: boolean;
  onOpenConversationDrawer?: () => void;
}

const Header: React.FC<HeaderProps> = ({ 
  onToggleNotification, 
  showNotificationPopup = false,
  onOpenConversationDrawer,
}) => {
  const { user, logout } = useAuth();
  const { unreadCount, fetchNotifications } = useNotifications();
  const location = useLocation();
  const navigate = useNavigate();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  // 定期刷新未读数量
  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(() => {
      fetchNotifications();
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // 路由变化时关闭移动端菜单
  useEffect(() => {
    setIsMobileMenuOpen(false);
    setIsUserMenuOpen(false);
  }, [location.pathname]);

  // 点击外部关闭用户菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('.user-menu-container')) {
        setIsUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleNavClick = (path: string) => {
    navigate(path);
    setIsMobileMenuOpen(false);
  };

  const handleLogout = () => {
    setIsUserMenuOpen(false);
    setIsMobileMenuOpen(false);
    logout();
  };

  const handleNotificationClick = () => {
    if (onToggleNotification) {
      onToggleNotification();
    } else {
      navigate('/notifications');
    }
    setIsMobileMenuOpen(false);
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <header className="app-header">
      {/* Logo */}
      <div className="header-logo" onClick={() => handleNavClick('/chat')}>
        <span className="logo-icon">🌊</span>
        <span className="logo-text">iFlow</span>
      </div>

      {/* 会话按钮区域 - 左侧 */}
      <div className="header-chat-buttons">
        <NewChatButton />
        <HistoryButton onClick={onOpenConversationDrawer} />
      </div>

      {/* Desktop Navigation */}
      <nav className="header-nav desktop-nav">
        <button 
          className={`nav-item ${isActive('/chat') ? 'active' : ''}`}
          onClick={() => handleNavClick('/chat')}
        >
          <span className="nav-icon">💬</span>
          <span className="nav-text">对话</span>
        </button>
        <button 
          className={`nav-item ${isActive('/tasks') ? 'active' : ''}`}
          onClick={() => handleNavClick('/tasks')}
        >
          <span className="nav-icon">⏰</span>
          <span className="nav-text">任务</span>
        </button>
        <button 
          className={`nav-item ${isActive('/notifications') ? 'active' : ''}`}
          onClick={handleNotificationClick}
        >
          <span className="nav-icon">🔔</span>
          <span className="nav-text">通知</span>
          {unreadCount > 0 && (
            <span className="notification-badge">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </button>
      </nav>

      {/* Mobile Menu Button */}
      <button 
        className="mobile-menu-btn"
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        aria-label="菜单"
      >
        <span className={`hamburger ${isMobileMenuOpen ? 'open' : ''}`}>
          <span></span>
          <span></span>
          <span></span>
        </span>
      </button>

      {/* User Menu (Desktop) */}
      <div className="user-menu-container desktop-user-menu">
        <button 
          className="user-menu-trigger"
          onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
        >
          <span className="user-avatar">{user?.username?.charAt(0).toUpperCase() || '?'}</span>
          <span className="user-name">{user?.username || '用户'}</span>
          <span className={`dropdown-arrow ${isUserMenuOpen ? 'open' : ''}`}>▼</span>
        </button>
        {isUserMenuOpen && (
          <div className="user-menu-dropdown">
            <div className="user-info">
              <span className="user-email">{user?.email || ''}</span>
            </div>
            <div className="menu-divider"></div>
            <button className="menu-item" onClick={handleLogout}>
              <span className="menu-icon">🚪</span>
              退出登录
            </button>
          </div>
        )}
      </div>

      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <div className="mobile-menu-overlay" onClick={() => setIsMobileMenuOpen(false)}>
          <div className="mobile-menu" onClick={(e) => e.stopPropagation()}>
            {/* User Info in Mobile Menu */}
            <div className="mobile-user-info">
              <span className="mobile-user-avatar">{user?.username?.charAt(0).toUpperCase() || '?'}</span>
              <div className="mobile-user-details">
                <span className="mobile-user-name">{user?.username || '用户'}</span>
                <span className="mobile-user-email">{user?.email || ''}</span>
              </div>
            </div>

            <div className="mobile-menu-divider"></div>

            {/* Mobile Navigation */}
            <nav className="mobile-nav">
              <button 
                className={`mobile-nav-item ${isActive('/chat') ? 'active' : ''}`}
                onClick={() => handleNavClick('/chat')}
              >
                <span className="nav-icon">💬</span>
                <span className="nav-text">对话</span>
              </button>
              <button 
                className={`mobile-nav-item ${isActive('/tasks') ? 'active' : ''}`}
                onClick={() => handleNavClick('/tasks')}
              >
                <span className="nav-icon">⏰</span>
                <span className="nav-text">任务</span>
              </button>
              <button 
                className={`mobile-nav-item ${isActive('/notifications') ? 'active' : ''}`}
                onClick={() => handleNavClick('/notifications')}
              >
                <span className="nav-icon">🔔</span>
                <span className="nav-text">通知</span>
                {unreadCount > 0 && (
                  <span className="mobile-notification-badge">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </button>
            </nav>

            <div className="mobile-menu-divider"></div>

            {/* Logout Button */}
            <button className="mobile-logout-btn" onClick={handleLogout}>
              <span className="menu-icon">🚪</span>
              退出登录
            </button>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;
