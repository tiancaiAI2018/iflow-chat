import { useState, useEffect, useRef, useCallback } from 'react';
import type { WSMessage, ToolCall, Notification } from '../types';

interface UseWebSocketOptions {
  url: string;
  onMessage?: (message: WSMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  sendMessage: (message: WSMessage) => void;
  disconnect: () => void;
  reconnect: () => void;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts = 5,
    reconnectInterval = 3000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  // 清理重连定时器
  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  // 连接 WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || isConnecting) {
      return;
    }

    if (!url) {
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        setIsConnecting(false);
        setError(null);
        reconnectCountRef.current = 0;
        onConnect?.();
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const message = JSON.parse(event.data) as WSMessage;
          onMessage?.(message);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onerror = (event) => {
        if (!mountedRef.current) return;
        setError('WebSocket 连接错误');
        setIsConnecting(false);
        onError?.(event);
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        setIsConnecting(false);
        onDisconnect?.();

        // 自动重连
        if (reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++;
          reconnectTimeoutRef.current = setTimeout(() => {
            if (mountedRef.current) {
              connect();
            }
          }, reconnectInterval);
        } else {
          setError('连接已断开，请刷新页面重试');
        }
      };
    } catch (e) {
      setIsConnecting(false);
      setError('无法建立 WebSocket 连接');
    }
  }, [url, isConnecting, onConnect, onDisconnect, onError, onMessage, reconnectAttempts, reconnectInterval]);

  // 发送消息
  const sendMessage = useCallback((message: WSMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }, []);

  // 断开连接
  const disconnect = useCallback(() => {
    clearReconnectTimeout();
    reconnectCountRef.current = reconnectAttempts; // 阻止自动重连
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
    setIsConnecting(false);
  }, [clearReconnectTimeout, reconnectAttempts]);

  // 手动重连
  const reconnect = useCallback(() => {
    disconnect();
    reconnectCountRef.current = 0;
    setError(null);
    setTimeout(() => connect(), 100);
  }, [connect, disconnect]);

  // 初始化连接
  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearReconnectTimeout();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [url]); // 仅在 URL 变化时重新连接

  return {
    isConnected,
    isConnecting,
    error,
    sendMessage,
    disconnect,
    reconnect,
  };
}

// 用于管理对话状态的 hook
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
  toolCalls?: ToolCall[];
  created_at: string;
}

interface UseChatOptions {
  userId: number;
  wsUrl: string;
  onNotification?: (notification: Notification) => void;
}

interface UseChatReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  isConnected: boolean;
  error: string | null;
  sendMessage: (content: string) => void;
  clearMessages: () => void;
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const { userId, wsUrl, onNotification } = options;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentAssistantMessage, setCurrentAssistantMessage] = useState<string>('');
  const [currentToolCalls, setCurrentToolCalls] = useState<ToolCall[]>([]);

  // 处理 WebSocket 消息
  const handleWSMessage = useCallback((message: WSMessage) => {
    switch (message.type) {
      case 'assistant_message':
        if (message.is_delta) {
          // 流式消息：追加内容
          setCurrentAssistantMessage((prev) => prev + (message.content || ''));
          setIsStreaming(!message.is_finished);
        } else {
          // 完整消息：直接设置
          setCurrentAssistantMessage(message.content || '');
          setIsStreaming(false);
        }

        // 消息结束，添加到消息列表
        if (message.is_finished) {
          setMessages((prev) => [
            ...prev,
            {
              id: `msg-${Date.now()}`,
              role: 'assistant',
              content: currentAssistantMessage + (message.content || ''),
              toolCalls: currentToolCalls.length > 0 ? currentToolCalls : undefined,
              created_at: new Date().toISOString(),
            },
          ]);
          setCurrentAssistantMessage('');
          setCurrentToolCalls([]);
        }
        break;

      case 'tool_call':
        // 工具调用消息
        const newToolCall: ToolCall = {
          tool_name: message.tool_name || 'unknown',
          arguments: message.arguments || {},
          status: message.status || 'pending',
          result: message.result,
        };
        setCurrentToolCalls((prev) => {
          // 更新已存在的工具调用或添加新的
          const existingIndex = prev.findIndex(
            (tc) => tc.tool_name === newToolCall.tool_name
          );
          if (existingIndex >= 0) {
            const updated = [...prev];
            updated[existingIndex] = newToolCall;
            return updated;
          }
          return [...prev, newToolCall];
        });
        break;

      case 'notification':
        if (message.notification) {
          onNotification?.(message.notification);
        }
        break;

      case 'error':
        console.error('WebSocket error message:', message.message);
        break;

      default:
        break;
    }
  }, [currentAssistantMessage, currentToolCalls, onNotification]);

  const {
    isConnected,
    error: wsError,
    sendMessage: wsSendMessage,
  } = useWebSocket({
    url: wsUrl,
    onMessage: handleWSMessage,
  });

  // 发送消息
  const sendMessage = useCallback((content: string) => {
    if (!content.trim()) return;

    // 添加用户消息到列表
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // 发送到 WebSocket
    wsSendMessage({
      type: 'chat',
      content,
    });

    setIsStreaming(true);
  }, [wsSendMessage]);

  // 清空消息
  const clearMessages = useCallback(() => {
    setMessages([]);
    setCurrentAssistantMessage('');
    setCurrentToolCalls([]);
  }, []);

  // 合并当前正在流式输出的消息
  const allMessages = [...messages];
  if (currentAssistantMessage || currentToolCalls.length > 0) {
    allMessages.push({
      id: 'streaming',
      role: 'assistant',
      content: currentAssistantMessage,
      isStreaming: true,
      toolCalls: currentToolCalls,
      created_at: new Date().toISOString(),
    });
  }

  return {
    messages: allMessages,
    isStreaming,
    isConnected,
    error: wsError,
    sendMessage,
    clearMessages,
  };
}

export default useWebSocket;
