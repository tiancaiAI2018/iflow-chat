import React, { createContext, useContext, useState, useCallback, useRef, ReactNode, useEffect } from 'react';
import type { WSMessage, ToolCall, Notification, Conversation, ConversationResponse, Message } from '../types';
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
  // 会话相关
  conversations: ConversationResponse[];
  currentConversationId: number | null;
  currentConversation: ConversationResponse | null;
  isLoadingConversations: boolean;
  loadConversations: () => Promise<void>;
  switchConversation: (conversationId: number) => Promise<void>;
  createNewConversation: (firstMessage?: string) => Promise<ConversationResponse | null>;
  deleteConversation: (conversationId: number) => Promise<boolean>;
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
  
  // 会话相关状态
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);

  // 使用 ref 追踪 WebSocket 和流式内容
  const wsRef = useRef<WebSocket | null>(null);
  const streamingContentRef = useRef<string>('');
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectCountRef = useRef(0);
  const mountedRef = useRef(true);

  // 当前会话对象
  const currentConversation = conversations.find(c => c.id === currentConversationId) || null;

  // 加载会话列表
  const loadConversations = useCallback(async () => {
    if (!user) return;
    
    setIsLoadingConversations(true);
    try {
      const response = await apiService.getConversations({ page: 1, page_size: 50 });
      setConversations(response.conversations);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setIsLoadingConversations(false);
    }
  }, [user]);

  // 切换会话
  const switchConversation = useCallback(async (conversationId: number) => {
    if (currentConversationId === conversationId) return;
    
    try {
      // 清空当前消息
      setMessages([]);
      setCurrentAssistantMessage('');
      streamingContentRef.current = '';
      
      // 获取会话详情和历史消息
      const response = await apiService.getConversation(conversationId);
      
      // 设置当前会话ID
      setCurrentConversationId(conversationId);
      
      // 加载历史消息
      const historyMessages: ChatMessage[] = response.messages.map((msg: Message) => ({
        id: `msg-${msg.id}`,
        role: msg.role,
        content: msg.content,
        created_at: msg.created_at,
      }));
      setMessages(historyMessages);
      
      // 发送切换会话消息到 WebSocket
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'switch_conversation',
          conversation_id: conversationId,
        }));
      }
      
      setError(null);
    } catch (err) {
      console.error('Failed to switch conversation:', err);
      setError('切换会话失败');
    }
  }, [currentConversationId]);

  // 创建新会话
  const createNewConversation = useCallback(async (_firstMessage?: string): Promise<ConversationResponse | null> => {
    if (!user) return null;
    
    try {
      // 不传 first_message，让后端使用默认标题，确保快速返回
      const response = await apiService.createConversation();
      
      const newConversation = response.conversation;
      
      // 添加到会话列表开头
      setConversations(prev => [newConversation, ...prev]);
      
      // 切换到新会话
      setCurrentConversationId(newConversation.id);
      
      // 清空消息
      setMessages([]);
      setCurrentAssistantMessage('');
      streamingContentRef.current = '';
      
      // 发送切换会话消息到 WebSocket
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'switch_conversation',
          conversation_id: newConversation.id,
        }));
      }
      
      return newConversation;
    } catch (err) {
      console.error('Failed to create conversation:', err);
      setError('创建会话失败，请稍后重试');
      return null;
    }
  }, [user]);

  // 删除会话
  const deleteConversation = useCallback(async (conversationId: number): Promise<boolean> => {
    try {
      await apiService.deleteConversation(conversationId);
      
      // 从列表中移除
      setConversations(prev => prev.filter(c => c.id !== conversationId));
      
      // 如果删除的是当前会话，切换到第一个可用会话或清空
      if (currentConversationId === conversationId) {
        setMessages([]);
        setCurrentConversationId(null);
        setCurrentAssistantMessage('');
        streamingContentRef.current = '';
      }
      
      return true;
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      setError('删除会话失败');
      return false;
    }
  }, [currentConversationId]);

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

            // 刷新会话列表以更新标题和时间
            loadConversations();
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
  }, [onNotification, loadConversations]);

  // 使用 ref 保存 currentConversationId，避免 connect 函数依赖变化导致 WebSocket 重建
  const currentConversationIdRef = useRef(currentConversationId);
  currentConversationIdRef.current = currentConversationId;

  // 连接 WebSocket
  const connect = useCallback(() => {
    if (!user) return;
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    const wsUrl = apiService.getWebSocketUrl(user.id);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = async () => {
      if (!mountedRef.current) return;
      setIsConnected(true);
      setError(null);
      reconnectCountRef.current = 0;
      console.log('WebSocket connected');
      
      // 如果有当前会话，发送切换消息（使用 ref 获取最新值）
      if (currentConversationIdRef.current) {
        ws.send(JSON.stringify({
          type: 'switch_conversation',
          conversation_id: currentConversationIdRef.current,
        }));
      } else {
        // 没有当前会话时，自动创建新会话
        try {
          const response = await apiService.createConversation();
          if (response?.conversation && mountedRef.current) {
            const newConv = response.conversation;
            setConversations(prev => [newConv, ...prev]);
            setCurrentConversationId(newConv.id);
            setMessages([]);
            console.log('Auto created conversation:', newConv.id);
          }
        } catch (err) {
          console.error('Failed to auto create conversation:', err);
          if (mountedRef.current) {
            setError('iFlow 未连接，请稍后重试');
            setIsConnected(false);
          }
        }
      }
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

  // 初始化连接和加载会话
  useEffect(() => {
    mountedRef.current = true;
    
    if (user) {
      connect();
      loadConversations();
    }

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
  }, [user, connect, loadConversations]);

  // 发送消息
  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim()) return;
    
    // 检查 WebSocket 连接状态
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket 未连接，正在重连...');
      return;
    }

    streamingContentRef.current = '';
    setCurrentAssistantMessage('');

    // 如果没有当前会话，先创建一个新会话
    let conversationIdToSend = currentConversationId;
    if (!conversationIdToSend) {
      try {
        const newConv = await createNewConversation();
        if (!newConv) {
          setError('创建会话失败，请刷新页面重试');
          return;
        }
        conversationIdToSend = newConv.id;
      } catch (err) {
        console.error('Error creating conversation:', err);
        setError('创建会话失败，请稍后重试');
        return;
      }
    }

    // 添加用户消息到列表
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // 通过 WebSocket 发送
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'chat',
        content,
        conversation_id: conversationIdToSend,
      }));
      setIsWaiting(true);
      setIsStreaming(true);
    } else {
      setError('连接已断开，请刷新页面重试');
    }
  }, [currentConversationId, createNewConversation]);

  // 清空消息（保留用于清空当前显示）
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
    // 会话相关
    conversations,
    currentConversationId,
    currentConversation,
    isLoadingConversations,
    loadConversations,
    switchConversation,
    createNewConversation,
    deleteConversation,
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
