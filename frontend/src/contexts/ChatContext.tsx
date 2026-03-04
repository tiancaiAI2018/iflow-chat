import React, { createContext, useContext, useState, useCallback, useRef, ReactNode, useEffect } from 'react';
import type { WSMessage, ToolCall, Notification } from '../types';
import { apiService } from '../services/api';
import { useAuth } from '../hooks/useAuth';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool_call';
  content: string;
  isStreaming?: boolean;
  isWaiting?: boolean;
  toolCalls?: ToolCall[];
  toolCall?: ToolCall;
  created_at: string;
}

interface ChatContextValue {
  messages: ChatMessage[];
  isStreaming: boolean;
  isWaiting: boolean;
  isConnected: boolean;
  error: string | null;
  sendMessage: (content: string) => void;
  clearMessages: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

interface ChatProviderProps {
  children: ReactNode;
  onNotification?: (notification: Notification) => void;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children, onNotification }) => {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isWaiting, setIsWaiting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentAssistantMessage, setCurrentAssistantMessage] = useState<string>('');

  // 使用 ref 追踪 WebSocket 和流式内容
  const wsRef = useRef<WebSocket | null>(null);
  const streamingContentRef = useRef<string>('');
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectCountRef = useRef(0);
  const mountedRef = useRef(true);

  // 处理 WebSocket 消息
  const handleWSMessage = useCallback((event: MessageEvent) => {
    if (!mountedRef.current) return;
    
    try {
      const message = JSON.parse(event.data) as WSMessage;
      setIsWaiting(false);

      switch (message.type) {
        case 'assistant_message':
          if (message.is_delta) {
            if (message.content) {
              const newContent = streamingContentRef.current + message.content;
              streamingContentRef.current = newContent;
              setCurrentAssistantMessage(newContent);
            }
            setIsStreaming(!message.is_finished);
          } else if (message.content) {
            streamingContentRef.current = message.content;
            setCurrentAssistantMessage(message.content);
            setIsStreaming(false);
          }

          if (message.is_finished) {
            const finalContent = streamingContentRef.current;
            
            if (finalContent) {
              setMessages((prev) => [
                ...prev,
                {
                  id: `msg-${Date.now()}`,
                  role: 'assistant',
                  content: finalContent,
                  created_at: new Date().toISOString(),
                },
              ]);
            }
            streamingContentRef.current = '';
            setCurrentAssistantMessage('');
            setIsStreaming(false);
            
            setMessages((prev) => 
              prev.map((msg) => {
                if (msg.role === 'tool_call' && msg.toolCall && msg.toolCall.status !== 'completed') {
                  return {
                    ...msg,
                    toolCall: { ...msg.toolCall, status: 'completed' as const },
                  };
                }
                return msg;
              })
            );
          }
          break;

        case 'tool_call':
          const newToolCall: ToolCall = {
            tool_id: message.tool_id,
            tool_name: message.tool_name || 'unknown',
            arguments: message.arguments || {},
            status: message.status || 'in_progress',
            result: message.result,
          };
          
          const toolKey = message.tool_id || message.tool_name || 'unknown';
          
          setMessages((prev) => {
            const existingIndex = prev.findIndex(
              (msg) => msg.role === 'tool_call' && msg.toolCall?.tool_id === message.tool_id
            );
            
            if (existingIndex >= 0) {
              const updated = [...prev];
              updated[existingIndex] = {
                ...updated[existingIndex],
                toolCall: newToolCall,
              };
              return updated;
            } else {
              return [
                ...prev,
                {
                  id: `tool-${Date.now()}-${toolKey}`,
                  role: 'tool_call' as const,
                  content: '',
                  toolCall: newToolCall,
                  created_at: new Date().toISOString(),
                },
              ];
            }
          });
          break;

        case 'notification':
          if (message.notification) {
            onNotification?.(message.notification);
          }
          break;

        case 'error':
          console.error('WebSocket error message:', message.message);
          setError(message.message || '未知错误');
          break;

        default:
          break;
      }
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e);
    }
  }, [onNotification]);

  // 连接 WebSocket
  const connect = useCallback(() => {
    if (!user) return;
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    const wsUrl = apiService.getWebSocketUrl(user.id);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setIsConnected(true);
      setError(null);
      reconnectCountRef.current = 0;
      console.log('WebSocket connected');
    };

    ws.onmessage = handleWSMessage;

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setError('WebSocket 连接错误');
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setIsConnected(false);
      console.log('WebSocket disconnected');

      // 自动重连（最多5次）
      if (reconnectCountRef.current < 5) {
        reconnectCountRef.current++;
        reconnectTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) {
            console.log(`Reconnecting... attempt ${reconnectCountRef.current}`);
            connect();
          }
        }, 3000);
      } else {
        setError('连接已断开，请刷新页面重试');
      }
    };
  }, [user, handleWSMessage]);

  // 初始化连接
  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  // 发送消息
  const sendMessage = useCallback((content: string) => {
    if (!content.trim()) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket 未连接');
      return;
    }

    streamingContentRef.current = '';
    setCurrentAssistantMessage('');

    // 添加用户消息到列表
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // 通过 WebSocket 发送
    wsRef.current.send(JSON.stringify({
      type: 'chat',
      content,
    }));

    setIsWaiting(true);
    setIsStreaming(true);
  }, []);

  // 清空消息
  const clearMessages = useCallback(() => {
    setMessages([]);
    setCurrentAssistantMessage('');
    streamingContentRef.current = '';
  }, []);

  // 合并当前正在流式输出的消息
  const allMessages = [...messages];
  if (currentAssistantMessage) {
    allMessages.push({
      id: 'streaming',
      role: 'assistant',
      content: currentAssistantMessage,
      isStreaming: true,
      created_at: new Date().toISOString(),
    });
  }

  const value: ChatContextValue = {
    messages: allMessages,
    isStreaming,
    isWaiting,
    isConnected,
    error,
    sendMessage,
    clearMessages,
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
};

export function useChatContext(): ChatContextValue {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
}

export default ChatContext;