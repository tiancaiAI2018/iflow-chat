import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useChat } from '../../hooks/useWebSocket';
import { apiService } from '../../services/api';
import Message from './Message';
import MessageInput from './MessageInput';
import './Chat.css';

interface ChatProps {
  onNotification?: (notification: { id: string; content: string; read: boolean; created_at: string }) => void;
}

const Chat: React.FC<ChatProps> = ({ onNotification }) => {
  const { user, token } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');

  // 获取 WebSocket URL
  const wsUrl = user ? apiService.getWebSocketUrl(user.id) : '';

  // 使用 useChat hook 管理对话状态
  const {
    messages,
    isStreaming,
    isConnected,
    error,
    sendMessage,
    clearMessages,
  } = useChat({
    userId: user?.id || 0,
    wsUrl,
    onNotification,
  });

  // 加载历史消息
  useEffect(() => {
    const loadHistory = async () => {
      if (!user) return;
      
      setIsLoadingHistory(true);
      try {
        const response = await apiService.getChatHistory({ page: 1, page_size: 50 });
        // 历史消息会在 Chat 组件内部处理，这里只是预加载
        // 如果需要显示历史消息，可以扩展 useChat 来支持初始化消息
      } catch (err) {
        console.error('Failed to load chat history:', err);
      } finally {
        setIsLoadingHistory(false);
      }
    };

    loadHistory();
  }, [user]);

  // 监听连接状态
  useEffect(() => {
    setConnectionStatus(isConnected ? 'connected' : 'connecting');
  }, [isConnected]);

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 消息更新时滚动到底部
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 处理发送消息
  const handleSend = (content: string) => {
    sendMessage(content);
  };

  // 处理清空对话
  const handleClearChat = async () => {
    if (window.confirm('确定要清空所有对话记录吗？')) {
      try {
        await apiService.clearChatHistory();
        clearMessages();
      } catch (err) {
        console.error('Failed to clear chat history:', err);
      }
    }
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
        {isLoadingHistory && (
          <div className="loading-indicator">加载历史消息...</div>
        )}
        
        {messages.length === 0 && !isLoadingHistory && (
          <div className="empty-chat">
            <div className="empty-chat-icon">💬</div>
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
            toolCalls={msg.toolCalls}
            created_at={msg.created_at}
          />
        ))}
        
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
        <button 
          className="clear-chat-btn" 
          onClick={handleClearChat}
          title="清空对话"
        >
          🗑️
        </button>
      </div>
    </div>
  );
};

export default Chat;
