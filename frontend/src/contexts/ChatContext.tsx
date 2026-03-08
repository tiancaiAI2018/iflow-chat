import React, { createContext, useContext, useState, useCallback, useRef, ReactNode, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { WSMessage, ToolCall, Notification, Conversation, ConversationResponse, Message } from '../types';
import { apiService } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import type { Attachment } from '../components/Chat/MessageInput';

// 文件数据格式（用于 WebSocket 传输）
interface FileData {
  name: string;
  type: 'image' | 'file' | 'audio';
  mimeType: string;
  data: string; // base64 编码的数据
  size: number;
}

// 消息中的附件信息（用于显示）
interface MessageAttachment {
  name: string;
  type: 'image' | 'file';
  size: number;
  preview?: string;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool_call';
  content: string;
  isStreaming?: boolean;
  isWaiting?: boolean;
  toolCalls?: ToolCall[];
  toolCall?: ToolCall;
  created_at: string;
  attachments?: MessageAttachment[];
}

interface ChatContextValue {
  messages: ChatMessage[];
  isStreaming: boolean;
  isWaiting: boolean;
  isConnected: boolean;
  error: string | null;
  sendMessage: (content: string, attachments?: Attachment[]) => void;
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
  // 工作目录选择相关
  showWorkspaceModal: boolean;
  isCreatingConversation: boolean;
  openWorkspaceModal: () => void;
  closeWorkspaceModal: () => void;
  createNewConversationWithWorkspace: (workingDirectory: string) => Promise<ConversationResponse | null>;
}

const ChatContext = createContext<ChatContextValue | null>(null);

interface ChatProviderProps {
  children: ReactNode;
  onNotification?: (notification: Notification) => void;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children, onNotification }) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { conversationId: urlConversationId } = useParams<{ conversationId?: string }>();
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
  
  // 工作目录选择相关状态
  const [showWorkspaceModal, setShowWorkspaceModal] = useState(false);
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);

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
      
      // 更新 URL（不触发重新导航）
      navigate(`/chat/${conversationId}`, { replace: true });
      
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
  }, [currentConversationId, navigate]);

  // 创建新会话（支持工作目录参数）
  const createNewConversation = useCallback(async (_firstMessage?: string): Promise<ConversationResponse | null> => {
    // 打开工作目录选择对话框，而不是直接创建
    setShowWorkspaceModal(true);
    return null;
  }, []);

  // 打开工作目录选择对话框
  const openWorkspaceModal = useCallback(() => {
    setShowWorkspaceModal(true);
  }, []);

  // 关闭工作目录选择对话框
  const closeWorkspaceModal = useCallback(() => {
    if (!isCreatingConversation) {
      setShowWorkspaceModal(false);
    }
  }, [isCreatingConversation]);

  // 创建新会话并指定工作目录
  const createNewConversationWithWorkspace = useCallback(async (workingDirectory: string): Promise<ConversationResponse | null> => {
    if (!user) return null;
    
    setIsCreatingConversation(true);
    
    try {
      // 调用后端 API 创建会话，传递 working_directory 参数
      const response = await apiService.createConversation({ working_directory: workingDirectory });
      
      const newConversation = response.conversation;
      
      // 添加到会话列表开头
      setConversations(prev => [newConversation, ...prev]);
      
      // 切换到新会话
      setCurrentConversationId(newConversation.id);
      
      // 更新 URL
      navigate(`/chat/${newConversation.id}`, { replace: true });
      
      // 清空消息
      setMessages([]);
      setCurrentAssistantMessage('');
      streamingContentRef.current = '';
      
      // 关闭对话框
      setShowWorkspaceModal(false);
      
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
    } finally {
      setIsCreatingConversation(false);
    }
  }, [user, navigate]);

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
        // 更新 URL 到 /chat
        navigate('/chat', { replace: true });
      }
      
      return true;
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      setError('删除会话失败');
      return false;
    }
  }, [currentConversationId, navigate]);

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

      const isReconnect = reconnectCountRef.current > 0;
      console.log(`WebSocket connected (reconnect: ${isReconnect})`);

      // 如果是重连，尝试从 API 获取未消费的消息
      if (isReconnect) {
        try {
          console.log('Fetching pending messages after reconnect...');
          const response = await apiService.getPendingMessages(50);

          if (response.success && response.messages.length > 0) {
            console.log(`Recovered ${response.messages.length} pending messages`);

            // 处理恢复的消息
            let accumulatedContent = '';

            for (const msg of response.messages) {
              if (msg.type === 'stream') {
                // 流式消息：累积内容
                accumulatedContent += msg.content;

                // 如果有 conversation_id，切换到对应会话
                if (msg.conversation_id && msg.conversation_id !== currentConversationIdRef.current) {
                  setCurrentConversationId(msg.conversation_id);
                  // 发送切换会话消息
                  ws.send(JSON.stringify({
                    type: 'switch_conversation',
                    conversation_id: msg.conversation_id,
                  }));
                }
              } else if (msg.type === 'complete') {
                // 完整消息：显示为 assistant 消息
                setMessages((prev) => [
                  ...prev,
                  {
                    id: `recovered-${Date.now()}-${Math.random()}`,
                    role: 'assistant',
                    content: accumulatedContent || msg.content,
                    created_at: msg.created_at || new Date().toISOString(),
                  },
                ]);
                accumulatedContent = '';
              }
            }

            // 如果还有未完成的流式内容，显示为正在流式输出
            if (accumulatedContent) {
              streamingContentRef.current = accumulatedContent;
              setCurrentAssistantMessage(accumulatedContent);
              setIsStreaming(true);
            }
          }
        } catch (err) {
          console.error('Failed to fetch pending messages:', err);
          // 即使获取失败，也继续正常连接
        }
      }

      reconnectCountRef.current = 0;

      // 如果有当前会话，发送切换消息（使用 ref 获取最新值）
      if (currentConversationIdRef.current) {
        ws.send(JSON.stringify({
          type: 'switch_conversation',
          conversation_id: currentConversationIdRef.current,
        }));
      }
      // 没有当前会话时，不自动创建，而是让页面弹出工作目录选择对话框
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

      // 无限自动重连，每 1 秒尝试一次
      reconnectCountRef.current++;
      reconnectTimeoutRef.current = setTimeout(() => {
        if (mountedRef.current) {
          console.log(`Reconnecting... attempt ${reconnectCountRef.current}`);
          connect();
        }
      }, 1000);
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

  // 用于跟踪是否已处理过 URL 恢复
  const urlRestoredRef = useRef(false);

  // 从 URL 恢复对话（页面刷新后）
  useEffect(() => {
    if (!user || !urlConversationId) {
      urlRestoredRef.current = false;
      return;
    }
    
    const conversationId = parseInt(urlConversationId, 10);
    if (isNaN(conversationId)) return;
    
    // 已经恢复过或者当前已经是该对话
    if (urlRestoredRef.current || currentConversationId === conversationId) return;
    
    // 会话列表还没加载完，等待
    if (conversations.length === 0) return;
    
    // 检查会话是否存在
    if (!conversations.find(c => c.id === conversationId)) {
      // 会话不存在，跳转回 /chat
      navigate('/chat', { replace: true });
      return;
    }
    
    // 恢复对话
    urlRestoredRef.current = true;
    switchConversation(conversationId);
  }, [user, urlConversationId, conversations, currentConversationId, switchConversation, navigate]);

  // 将附件转换为 FileData 格式
  const convertAttachmentsToFileData = async (attachments: Attachment[]): Promise<FileData[]> => {
    const fileDataList: FileData[] = [];

    for (const attachment of attachments) {
      const file = attachment.file;
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const result = reader.result as string;
          // 移除 data:xxx;base64, 前缀
          const base64Data = result.split(',')[1];
          resolve(base64Data);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });

      // 确定文件类型
      let fileType: 'image' | 'file' | 'audio' = 'file';
      if (file.type.startsWith('image/')) {
        fileType = 'image';
      } else if (file.type.startsWith('audio/')) {
        fileType = 'audio';
      }

      fileDataList.push({
        name: file.name,
        type: fileType,
        mimeType: file.type,
        data: base64,
        size: file.size,
      });
    }

    return fileDataList;
  };

  // 发送消息
  const sendMessage = useCallback(async (content: string, attachments?: Attachment[]) => {
    if (!content.trim() && (!attachments || attachments.length === 0)) return;

    // 检查 WebSocket 连接状态
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket 未连接，正在重连...');
      return;
    }

    streamingContentRef.current = '';
    setCurrentAssistantMessage('');

    // 如果没有当前会话，使用默认工作目录自动创建一个新会话
    let conversationIdToSend = currentConversationId;
    if (!conversationIdToSend) {
      try {
        // 直接调用 API 创建会话（使用默认工作目录）
        const response = await apiService.createConversation({ working_directory: '/root/.iflow-bot/workspace' });
        if (response?.conversation) {
          const newConv = response.conversation;
          setConversations(prev => [newConv, ...prev]);
          setCurrentConversationId(newConv.id);
          conversationIdToSend = newConv.id;

          // 更新 URL
          navigate(`/chat/${newConv.id}`, { replace: true });

          // 发送切换会话消息到 WebSocket
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
              type: 'switch_conversation',
              conversation_id: newConv.id,
            }));
          }
        }
      } catch (err) {
        console.error('Error creating conversation:', err);
        setError('创建会话失败，请稍后重试');
        return;
      }
    }

    // 处理附件转换为 FileData
    let files: FileData[] = [];
    if (attachments && attachments.length > 0) {
      files = await convertAttachmentsToFileData(attachments);
    }

    // 添加用户消息到列表（包含附件预览）
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
      attachments: attachments?.map(a => ({
        name: a.file.name,
        type: a.type,
        size: a.file.size,
        preview: a.preview,
      })),
    };
    setMessages((prev) => [...prev, userMessage]);

    // 通过 WebSocket 发送
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const message: any = {
        type: 'chat',
        content,
        conversation_id: conversationIdToSend,
      };

      // 如果有附件，添加到消息中
      if (files.length > 0) {
        message.files = files;
      }

      wsRef.current.send(JSON.stringify(message));
      setIsWaiting(true);
      setIsStreaming(true);
    } else {
      setError('连接已断开，请刷新页面重试');
    }
  }, [currentConversationId, navigate]);

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
    // 工作目录选择相关
    showWorkspaceModal,
    isCreatingConversation,
    openWorkspaceModal,
    closeWorkspaceModal,
    createNewConversationWithWorkspace,
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
