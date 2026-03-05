import React from 'react';
import { useChatContext } from '../../contexts/ChatContext';
import './NewChatButton.css';

interface NewChatButtonProps {
  className?: string;
}

/**
 * 新建会话按钮组件
 * 点击打开工作目录选择对话框
 */
const NewChatButton: React.FC<NewChatButtonProps> = ({ className = '' }) => {
  const { openWorkspaceModal, isStreaming } = useChatContext();

  const handleClick = async () => {
    // 如果正在流式输出，不允许创建新会话
    if (isStreaming) return;
    
    // 打开工作目录选择对话框
    openWorkspaceModal();
  };

  return (
    <button
      type="button"
      className={`new-chat-button ${className}`}
      onClick={handleClick}
      disabled={isStreaming}
      title="新建对话"
      aria-label="新建对话"
    >
      <span className="new-chat-icon">+</span>
      <span className="new-chat-text">新对话</span>
    </button>
  );
};

export default NewChatButton;
