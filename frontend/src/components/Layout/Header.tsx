import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useNotifications } from '../../hooks/useNotifications';
import { NotificationBar } from '../Notification';
import NewChatButton from '../Chat/NewChatButton';
import HistoryButton from '../Chat/HistoryButton';
import PushKeySettings from '../Settings/PushKeySettings';
import { apiService } from '../../services/api';
import type { ACPInfoResponse } from '../../types';
import './Layout.css';

interface HeaderProps {
  onToggleNotification?: () => void;
  showNotificationPopup?: boolean;
  onOpenConversationDrawer?: () => void;
  showToolMessages?: boolean;
  onToggleShowToolMessages?: () => void;
}

const Header: React.FC<HeaderProps> = ({ 
  onToggleNotification, 
  showNotificationPopup = false,
  onOpenConversationDrawer,
  showToolMessages = true,
  onToggleShowToolMessages,
}) => {
  const { user, logout } = useAuth();
  const { unreadCount, fetchNotifications } = useNotifications();
  const location = useLocation();
  const navigate = useNavigate();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [acpInfo, setAcpInfo] = useState<ACPInfoResponse | null>(null);
  const [isLoadingACP, setIsLoadingACP] = useState(false);
  const [killingPort, setKillingPort] = useState<number | null>(null);
  const [showPushKeySettings, setShowPushKeySettings] = useState(false);

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

  // 加载 ACP 信息
  const loadACPInfo = useCallback(async () => {
    if (!user) return;
    setIsLoadingACP(true);
    try {
      const info = await apiService.getACPInfo();
      setAcpInfo(info);
    } catch (err) {
      console.error('Failed to load ACP info:', err);
    } finally {
      setIsLoadingACP(false);
    }
  }, [user]);

  // 用户菜单打开时加载 ACP 信息
  useEffect(() => {
    if (isUserMenuOpen) {
      loadACPInfo();
    }
  }, [isUserMenuOpen, loadACPInfo]);

  // Kill ACP 端口
  const handleKillPort = async (port: number) => {
    // 当前端口需要确认
    if (port === acpInfo?.current_port) {
      const confirmed = window.confirm('当前端口正在使用中，停止后会影响正在进行的对话。确定要停止吗？');
      if (!confirmed) {
        return;
      }
    }
    setKillingPort(port);
    try {
      await apiService.killACPPort(port);
      // 重新加载 ACP 信息
      await loadACPInfo();
    } catch (err: any) {
      console.error('Failed to kill port:', err);
      alert(err.response?.data?.detail || '停止端口失败');
    } finally {
      setKillingPort(null);
    }
  };

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
            
            {/* 显示工具消息开关 */}
            <div className="menu-setting-item">
              <span className="menu-setting-label">显示工具/计划消息</span>
              <button 
                className={`toggle-switch ${showToolMessages ? 'active' : ''}`}
                onClick={onToggleShowToolMessages}
                title={showToolMessages ? '点击隐藏工具和计划消息' : '点击显示工具和计划消息'}
              >
                <span className="toggle-slider"></span>
              </button>
            </div>
            
            <div className="menu-divider"></div>
            
            {/* ACP 端口列表 */}
            <div className="acp-section">
              <div className="acp-header">
                <span className="menu-icon">🔌</span>
                <span>ACP 连接</span>
                <button 
                  className="acp-refresh-btn"
                  onClick={loadACPInfo}
                  disabled={isLoadingACP}
                  title="刷新"
                >
                  {isLoadingACP ? '⏳' : '🔄'}
                </button>
              </div>
              
              {acpInfo && acpInfo.ports.length > 0 ? (
                <div className="acp-list">
                  {acpInfo.ports.map((port, index) => (
                    <div 
                      key={port} 
                      className={`acp-item ${port === acpInfo.current_port ? 'current' : 'old'}`}
                    >
                      <div className="acp-port-info">
                        <span className="acp-port">端口 {port}</span>
                        <span className="acp-status">
                          {port === acpInfo.current_port ? '● 当前' : '○ 旧连接'}
                        </span>
                      </div>
                      <button
                        className={`acp-kill-btn ${port === acpInfo.current_port ? 'current-kill' : ''}`}
                        onClick={() => handleKillPort(port)}
                        disabled={killingPort === port}
                        title={port === acpInfo.current_port ? '停止当前连接（会影响对话）' : '停止此连接'}
                      >
                        {killingPort === port ? '⏳' : '✕'}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="acp-empty">
                  {isLoadingACP ? '加载中...' : '暂无活跃连接'}
                </div>
              )}
            </div>
            
            <div className="menu-divider"></div>
            
            <button className="menu-item" onClick={() => {
              setIsUserMenuOpen(false);
              setShowPushKeySettings(true);
            }}>
              <span className="menu-icon">📱</span>
              推送设置
            </button>
            
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

            {/* Mobile Settings Section */}
            <div className="mobile-settings-section">
              {/* 显示工具消息开关 */}
              <div className="mobile-setting-item">
                <span className="menu-setting-label">显示工具/计划消息</span>
                <button 
                  className={`toggle-switch ${showToolMessages ? 'active' : ''}`}
                  onClick={onToggleShowToolMessages}
                  title={showToolMessages ? '点击隐藏工具和计划消息' : '点击显示工具和计划消息'}
                >
                  <span className="toggle-slider"></span>
                </button>
              </div>
              
              {/* ACP 端口列表 */}
              <div className="mobile-acp-section">
                <div className="acp-header">
                  <span className="menu-icon">🔌</span>
                  <span>ACP 连接</span>
                  <button 
                    className="acp-refresh-btn"
                    onClick={loadACPInfo}
                    disabled={isLoadingACP}
                    title="刷新"
                  >
                    {isLoadingACP ? '⏳' : '🔄'}
                  </button>
                </div>
                
                {acpInfo && acpInfo.ports.length > 0 ? (
                  <div className="acp-list">
                    {acpInfo.ports.map((port) => (
                      <div 
                        key={port} 
                        className={`acp-item ${port === acpInfo.current_port ? 'current' : 'old'}`}
                      >
                        <div className="acp-port-info">
                          <span className="acp-port">端口 {port}</span>
                          <span className="acp-status">
                            {port === acpInfo.current_port ? '● 当前' : '○ 旧连接'}
                          </span>
                        </div>
                        <button
                          className={`acp-kill-btn ${port === acpInfo.current_port ? 'current-kill' : ''}`}
                          onClick={() => handleKillPort(port)}
                          disabled={killingPort === port}
                          title={port === acpInfo.current_port ? '停止当前连接（会影响对话）' : '停止此连接'}
                        >
                          {killingPort === port ? '⏳' : '✕'}
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="acp-empty">
                    {isLoadingACP ? '加载中...' : '暂无活跃连接'}
                  </div>
                )}
              </div>
            </div>

            <div className="mobile-menu-divider"></div>

            {/* 推送设置按钮 */}
            <button 
              className="mobile-nav-item"
              onClick={() => {
                setIsMobileMenuOpen(false);
                setShowPushKeySettings(true);
              }}
            >
              <span className="nav-icon">📱</span>
              <span className="nav-text">推送设置</span>
            </button>

            <div className="mobile-menu-divider"></div>

            {/* Logout Button */}
            <button className="mobile-logout-btn" onClick={handleLogout}>
              <span className="menu-icon">🚪</span>
              退出登录
            </button>
          </div>
        </div>
      )}

      {/* 推送设置模态框 */}
      <PushKeySettings
        isOpen={showPushKeySettings}
        onClose={() => setShowPushKeySettings(false)}
        currentPushKey={user?.push_key}
        onUpdated={(pushKey) => {
          // 更新本地用户信息
          if (user) {
            const updatedUser = { ...user, push_key: pushKey };
            localStorage.setItem('user', JSON.stringify(updatedUser));
          }
        }}
      />
    </header>
  );
};

export default Header;
