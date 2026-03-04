import React, { useEffect, useRef, useState } from 'react';
import { useChatContext } from '../../contexts/ChatContext';
import { apiService } from '../../services/api';
import Message from './Message';
import MessageInput from './MessageInput';
import './Chat.css';

interface ChatProps {
  onNotification?: (notification: { id: string; content: string; read: boolean; created_at: string }) => void;
}

const Chat: React.FC<ChatProps> = ({ onNotification }) => {
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
    clearMessages,
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
        {messages.length === 0 && (
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
            isWaiting={msg.isWaiting}
            toolCalls={msg.toolCalls}
            toolCall={msg.toolCall}
            created_at={msg.created_at}
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
