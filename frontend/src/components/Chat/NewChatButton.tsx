import React from 'react';
import { useChatContext } from '../../contexts/ChatContext';
import './NewChatButton.css';

interface NewChatButtonProps {
  className?: string;
}

/**
 * 新建会话按钮组件
 * 点击创建新会话并切换到该会话
 */
const NewChatButton: React.FC<NewChatButtonProps> = ({ className = '' }) => {
  const { createNewConversation, isStreaming } = useChatContext();

  const handleClick = async () => {
    // 如果正在流式输出，不允许创建新会话
    if (isStreaming) return;
    
    try {
      await createNewConversation();
    } catch (error) {
      // 错误由 Context 处理，这里静默处理
      console.error('Failed to create conversation:', error);
    }
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
