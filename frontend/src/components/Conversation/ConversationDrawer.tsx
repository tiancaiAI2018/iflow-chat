import React, { useEffect, useRef, useCallback } from 'react';
import { useChatContext } from '../../contexts/ChatContext';
import type { ConversationResponse } from '../../types';
import ConversationItem from './ConversationItem';
import './Conversation.css';

interface ConversationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

const ConversationDrawer: React.FC<ConversationDrawerProps> = ({ isOpen, onClose }) => {
  const {
    conversations,
    currentConversationId,
    isLoadingConversations,
    loadConversations,
    switchConversation,
    deleteConversation,
    createNewConversation,
  } = useChatContext();

  const drawerRef = useRef<HTMLDivElement>(null);
  const touchStartX = useRef<number>(0);
  const touchCurrentX = useRef<number>(0);
  const isSwiping = useRef<boolean>(false);

  // 打开时加载会话列表
  useEffect(() => {
    if (isOpen) {
      loadConversations();
    }
  }, [isOpen, loadConversations]);

  // 点击遮罩关闭
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // 切换会话
  const handleSelectConversation = async (conversationId: number) => {
    await switchConversation(conversationId);
    onClose();
  };

  // 删除会话
  const handleDeleteConversation = async (conversationId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm('确定要删除这个会话吗？')) {
      await deleteConversation(conversationId);
    }
  };

  // 新建会话
  const handleNewChat = async () => {
    await createNewConversation();
    onClose();
  };

  // 触摸滑动关闭
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
    isSwiping.current = true;
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!isSwiping.current) return;
    touchCurrentX.current = e.touches[0].clientX;
    
    const diff = touchCurrentX.current - touchStartX.current;
    // 只响应向左滑动
    if (diff < 0 && drawerRef.current) {
      const translateX = Math.max(diff, -300);
      drawerRef.current.style.transform = `translateX(${translateX}px)`;
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (!isSwiping.current) return;
    isSwiping.current = false;

    const diff = touchCurrentX.current - touchStartX.current;
    
    // 滑动超过 100px 关闭抽屉
    if (diff < -100) {
      onClose();
    } else if (drawerRef.current) {
      drawerRef.current.style.transform = '';
    }
  }, [onClose]);

  // 格式化时间
  const formatTime = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
      return '昨天';
    } else if (diffDays < 7) {
      const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
      return weekdays[date.getDay()];
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
    }
  };

  // 按日期分组会话
  const groupedConversations = conversations.reduce<Record<string, ConversationResponse[]>>((groups, conv) => {
    const date = new Date(conv.updated_at);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    let groupKey: string;
    if (diffDays === 0) {
      groupKey = '今天';
    } else if (diffDays === 1) {
      groupKey = '昨天';
    } else if (diffDays < 7) {
      groupKey = '最近7天';
    } else {
      groupKey = '更早';
    }

    if (!groups[groupKey]) {
      groups[groupKey] = [];
    }
    groups[groupKey].push(conv);
    return groups;
  }, {});

  const groupOrder = ['今天', '昨天', '最近7天', '更早'];

  return (
    <div 
      className={`conversation-drawer-overlay ${isOpen ? 'open' : ''}`}
      onClick={handleOverlayClick}
    >
      <div
        ref={drawerRef}
        className={`conversation-drawer ${isOpen ? 'open' : ''}`}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {/* 头部 */}
        <div className="drawer-header">
          <h2 className="drawer-title">历史会话</h2>
          <button 
            className="new-chat-button"
            onClick={handleNewChat}
            title="新建会话"
          >
            <span className="new-chat-icon">+</span>
            <span className="new-chat-text">新对话</span>
          </button>
        </div>

        {/* 会话列表 */}
        <div className="drawer-content">
          {isLoadingConversations ? (
            <div className="drawer-loading">
              <div className="loading-spinner"></div>
              <span>加载中...</span>
            </div>
          ) : conversations.length === 0 ? (
            <div className="drawer-empty">
              <span className="empty-icon">📝</span>
              <span className="empty-text">暂无会话记录</span>
              <button className="start-chat-button" onClick={handleNewChat}>
                开始新对话
              </button>
            </div>
          ) : (
            <div className="conversation-groups">
              {groupOrder.map(group => 
                groupedConversations[group]?.length > 0 && (
                  <div key={group} className="conversation-group">
                    <div className="group-label">{group}</div>
                    {groupedConversations[group].map(conversation => (
                      <ConversationItem
                        key={conversation.id}
                        conversation={conversation}
                        isActive={conversation.id === currentConversationId}
                        onSelect={() => handleSelectConversation(conversation.id)}
                        onDelete={(e) => handleDeleteConversation(conversation.id, e)}
                        formatTime={formatTime}
                      />
                    ))}
                  </div>
                )
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ConversationDrawer;
