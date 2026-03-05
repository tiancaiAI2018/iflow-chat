import React, { useState, useRef } from 'react';
import type { ConversationResponse } from '../../types';

interface ConversationItemProps {
  conversation: ConversationResponse;
  isActive: boolean;
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
  formatTime: (date: string) => string;
}

const ConversationItem: React.FC<ConversationItemProps> = ({
  conversation,
  isActive,
  onSelect,
  onDelete,
  formatTime,
}) => {
  const [showDelete, setShowDelete] = useState(false);
  const [isLongPress, setIsLongPress] = useState(false);
  const longPressTimer = useRef<NodeJS.Timeout | null>(null);

  // 从工作目录路径中提取最后一级目录名
  const getWorkingDirectoryName = (path: string): string => {
    if (!path) return 'workspace';
    const parts = path.split('/').filter(Boolean);
    return parts[parts.length - 1] || 'workspace';
  };

  // 长按显示删除按钮
  const handleTouchStart = () => {
    longPressTimer.current = setTimeout(() => {
      setIsLongPress(true);
      setShowDelete(true);
    }, 500);
  };

  const handleTouchEnd = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

  // 右键菜单
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setShowDelete(true);
  };

  // 点击其他地方隐藏删除按钮
  const handleClickOutside = () => {
    if (showDelete) {
      setShowDelete(false);
    }
  };

  return (
    <div
      className={`conversation-item ${isActive ? 'active' : ''} ${showDelete ? 'show-delete' : ''}`}
      onClick={handleClickOutside}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      onContextMenu={handleContextMenu}
    >
      <div className="conversation-item-content" onClick={onSelect}>
        <div className="conversation-title">{conversation.title || '新对话'}</div>
        <div className="conversation-meta">
          <span className="conversation-workspace">📁 {getWorkingDirectoryName(conversation.working_directory)}</span>
          <span className="conversation-time">{formatTime(conversation.updated_at)}</span>
        </div>
      </div>
      
      <button
        className={`conversation-delete-btn ${showDelete ? 'visible' : ''}`}
        onClick={onDelete}
        title="删除会话"
      >
        🗑️
      </button>
    </div>
  );
};

export default ConversationItem;
