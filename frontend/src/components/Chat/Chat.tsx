import React, { useEffect, useRef, useState } from 'react';
import { useChatContext } from '../../contexts/ChatContext';
import Message from './Message';
import MessageInput from './MessageInput';
import ConversationDrawer from '../Conversation/ConversationDrawer';
import WorkspaceSelectModal from '../Workspace/WorkspaceSelectModal';
import './Chat.css';

interface ChatProps {
  onNotification?: (notification: { id: string; content: string; read: boolean; created_at: string }) => void;
  isConversationDrawerOpen?: boolean;
  onOpenConversationDrawer?: () => void;
  onCloseConversationDrawer?: () => void;
}

const Chat: React.FC<ChatProps> = ({ 
  onNotification,
  isConversationDrawerOpen = false,
  onOpenConversationDrawer,
  onCloseConversationDrawer,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');

  // 使用 ChatContext 获取共享的对话状态（WebSocket 连接由 Context 管理）
  const {
    messages,
    isStreaming,
    isWaiting,
    isConnected,
    error,
    sendMessage,
    // 会话相关状态
    currentConversation,
    currentConversationId,
    conversations,
    isLoadingConversations,
    loadConversations,
    switchConversation,
    createNewConversation,
    deleteConversation,
    // 工作目录选择相关
    showWorkspaceModal,
    isCreatingConversation,
    openWorkspaceModal,
    closeWorkspaceModal,
    createNewConversationWithWorkspace,
  } = useChatContext();

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 消息更新时滚动到底部
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 监听连接状态
  useEffect(() => {
    setConnectionStatus(isConnected ? 'connected' : 'connecting');
  }, [isConnected]);

  // 连接成功但没有当前会话时，自动弹出工作目录选择对话框
  useEffect(() => {
    if (isConnected && !currentConversationId && !showWorkspaceModal && conversations.length === 0) {
      // 延迟一点弹出，避免页面加载时的闪烁
      const timer = setTimeout(() => {
        openWorkspaceModal();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isConnected, currentConversationId, showWorkspaceModal, conversations.length, openWorkspaceModal]);

  // 处理发送消息（Context 内部会自动关联到当前会话，无会话时自动创建）
  const handleSend = (content: string, attachments?: any[]) => {
    sendMessage(content, attachments);
  };

  // 获取空聊天时的显示标题
  const getEmptyChatTitle = () => {
    if (currentConversation?.title) {
      return currentConversation.title;
    }
    return '新对话';
  };

  return (
    <div className="chat-container">
      {/* 连接状态指示器 */}
      <div className={`connection-status ${connectionStatus}`}>
        <span className="status-dot"></span>
        <span className="status-text">
          {connectionStatus === 'connected' ? '已连接' : 
           connectionStatus === 'connecting' ? '连接中...' : '已断开'}
        </span>
      </div>

      {/* 消息列表 */}
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="empty-chat">
            <div className="empty-chat-icon">💬</div>
            <div className="empty-chat-title">{getEmptyChatTitle()}</div>
            <div className="empty-chat-text">开始和 iFlow 对话吧！</div>
          </div>
        )}

        {messages.map((msg) => (
          <Message
            key={msg.id}
            id={msg.id}
            role={msg.role}
            content={msg.content}
            isStreaming={msg.isStreaming}
            isWaiting={msg.isWaiting}
            toolCalls={msg.toolCalls}
            toolCall={msg.toolCall}
            created_at={msg.created_at}
            attachments={msg.attachments}
          />
        ))}
        
        {/* 等待后端响应时显示机器人加载动画 */}
        {isWaiting && !messages.some(m => m.role === 'assistant' && m.isStreaming) && (
          <Message
            id="waiting"
            role="assistant"
            content=""
            isWaiting={true}
            created_at={new Date().toISOString()}
          />
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="chat-error">
          <span>{error}</span>
          <button onClick={() => window.location.reload()}>重新连接</button>
        </div>
      )}

      {/* 输入区域 */}
      <div className="chat-input-area">
        <MessageInput
          onSend={handleSend}
          disabled={!isConnected || isStreaming}
          placeholder={isStreaming ? '正在等待回复...' : '输入消息，按 Enter 发送...'}
        />
      </div>

      {/* 会话抽屉 */}
      <ConversationDrawer 
        isOpen={isConversationDrawerOpen} 
        onClose={onCloseConversationDrawer || (() => {})} 
      />

      {/* 工作目录选择对话框 */}
      <WorkspaceSelectModal
        isOpen={showWorkspaceModal}
        onClose={closeWorkspaceModal}
        onConfirm={createNewConversationWithWorkspace}
        isCreating={isCreatingConversation}
      />
    </div>
  );
};

export default Chat;
