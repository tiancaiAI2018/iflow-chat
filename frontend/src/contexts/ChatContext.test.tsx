/**
 * ChatContext 重连恢复逻辑测试
 *
 * 测试内容：
 * - WebSocket 重连后从 API 获取未消费消息
 * - 消息恢复处理（stream 和 complete 类型）
 * - 会话切换逻辑
 */
import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ChatProvider, useChatContext } from './ChatContext';
import { apiService } from '../services/api';
import { useAuth } from '../hooks/useAuth';

// Mock useAuth
jest.mock('../hooks/useAuth');
const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;

// Mock apiService
jest.mock('../services/api', () => ({
  apiService: {
    getWebSocketUrl: jest.fn(() => 'ws://localhost:8000/ws/1?token=test'),
    getConversations: jest.fn(() => Promise.resolve({ conversations: [], total: 0 })),
    getPendingMessages: jest.fn(() => Promise.resolve({ success: true, messages: [], count: 0 })),
    createConversation: jest.fn(),
  },
}));

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.OPEN;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(url: string) {
    MockWebSocket.instances.push(this);
  }

  send = jest.fn();
  close = jest.fn();

  simulateOpen() {
    if (this.onopen) {
      this.onopen(new Event('open'));
    }
  }

  simulateMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }
}

// 替换全局 WebSocket
// @ts-ignore
window.WebSocket = MockWebSocket;

// 测试组件
const TestComponent: React.FC = () => {
  const {
    messages,
    isConnected,
    currentConversationId,
  } = useChatContext();

  return (
    <div>
      <div data-testid="connected">{isConnected ? 'connected' : 'disconnected'}</div>
      <div data-testid="conversation-id">{currentConversationId || 'none'}</div>
      <div data-testid="messages">
        {messages.map((msg, i) => (
          <div key={i} data-testid={`message-${i}`}>
            {msg.role}: {msg.content}
          </div>
        ))}
      </div>
    </div>
  );
};

describe('ChatContext Reconnect Recovery', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    MockWebSocket.instances = [];
    jest.useFakeTimers();

    mockUseAuth.mockReturnValue({
      user: {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
        created_at: '2026-01-01T00:00:00Z',
        last_login: '2026-01-01T00:00:00Z',
      },
      token: 'test-token',
      isAuthenticated: true,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
      checkAuth: jest.fn(),
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should fetch pending messages on reconnect', async () => {
    const mockGetPendingMessages = apiService.getPendingMessages as jest.Mock;
    mockGetPendingMessages.mockResolvedValueOnce({
      success: true,
      messages: [],
      count: 0,
    });

    render(
      <ChatProvider>
        <TestComponent />
      </ChatProvider>
    );

    // 等待 WebSocket 连接
    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    const ws = MockWebSocket.instances[0];

    // 模拟初次连接
    await act(async () => {
      ws.simulateOpen();
    });

    // 首次连接不应该调用 getPendingMessages
    expect(mockGetPendingMessages).not.toHaveBeenCalled();

    // 模拟断开连接
    await act(async () => {
      ws.simulateClose();
    });

    // 等待重连（3秒后）
    await act(async () => {
      jest.advanceTimersByTime(3000);
    });

    // 等待新 WebSocket 创建
    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(2);
    });

    const newWs = MockWebSocket.instances[1];

    // 设置重连时返回的消息
    mockGetPendingMessages.mockResolvedValueOnce({
      success: true,
      messages: [
        {
          entry_id: '123-0',
          type: 'stream',
          content: 'Hello',
          is_delta: true,
          conversation_id: 42,
        },
        {
          entry_id: '123-1',
          type: 'complete',
          content: 'Hello World',
        },
      ],
      count: 2,
    });

    // 模拟重连
    await act(async () => {
      newWs.simulateOpen();
    });

    // 重连后应该调用 getPendingMessages
    await waitFor(() => {
      expect(mockGetPendingMessages).toHaveBeenCalledWith(50);
    });
  });

  it('should recover stream messages on reconnect', async () => {
    const mockGetPendingMessages = apiService.getPendingMessages as jest.Mock;

    render(
      <ChatProvider>
        <TestComponent />
      </ChatProvider>
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    const ws = MockWebSocket.instances[0];

    // 模拟首次连接
    await act(async () => {
      ws.simulateOpen();
    });

    // 模拟断开连接
    await act(async () => {
      ws.simulateClose();
    });

    // 等待重连
    await act(async () => {
      jest.advanceTimersByTime(3000);
    });

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(2);
    });

    const newWs = MockWebSocket.instances[1];

    // 设置待恢复的流式消息
    mockGetPendingMessages.mockResolvedValueOnce({
      success: true,
      messages: [
        { entry_id: '1-0', type: 'stream', content: 'Hello ', is_delta: true },
        { entry_id: '1-1', type: 'stream', content: 'World', is_delta: true },
        { entry_id: '1-2', type: 'complete', content: 'Hello World' },
      ],
      count: 3,
    });

    await act(async () => {
      newWs.simulateOpen();
    });

    await waitFor(() => {
      expect(mockGetPendingMessages).toHaveBeenCalled();
    });

    // 验证消息已恢复
    await waitFor(() => {
      const messages = screen.queryAllByTestId(/message-/);
      expect(messages.length).toBeGreaterThan(0);
    });
  });

  it('should switch conversation when recovered message has conversation_id', async () => {
    const mockGetPendingMessages = apiService.getPendingMessages as jest.Mock;

    render(
      <ChatProvider>
        <TestComponent />
      </ChatProvider>
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    const ws = MockWebSocket.instances[0];

    await act(async () => {
      ws.simulateOpen();
    });

    await act(async () => {
      ws.simulateClose();
    });

    await act(async () => {
      jest.advanceTimersByTime(3000);
    });

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(2);
    });

    const newWs = MockWebSocket.instances[1];

    mockGetPendingMessages.mockResolvedValueOnce({
      success: true,
      messages: [
        {
          entry_id: '1-0',
          type: 'stream',
          content: 'Test',
          is_delta: true,
          conversation_id: 99,
        },
      ],
      count: 1,
    });

    await act(async () => {
      newWs.simulateOpen();
    });

    await waitFor(() => {
      expect(newWs.send).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'switch_conversation',
          conversation_id: 99,
        })
      );
    });
  });

  it('should handle empty pending messages gracefully', async () => {
    const mockGetPendingMessages = apiService.getPendingMessages as jest.Mock;
    mockGetPendingMessages.mockResolvedValueOnce({
      success: true,
      messages: [],
      count: 0,
    });

    render(
      <ChatProvider>
        <TestComponent />
      </ChatProvider>
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    const ws = MockWebSocket.instances[0];

    await act(async () => {
      ws.simulateOpen();
    });

    await act(async () => {
      ws.simulateClose();
    });

    await act(async () => {
      jest.advanceTimersByTime(3000);
    });

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(2);
    });

    const newWs = MockWebSocket.instances[1];

    await act(async () => {
      newWs.simulateOpen();
    });

    await waitFor(() => {
      expect(mockGetPendingMessages).toHaveBeenCalled();
    });

    // 连接应该正常建立
    await waitFor(() => {
      expect(screen.getByTestId('connected')).toHaveTextContent('connected');
    });
  });

  it('should handle API error gracefully on reconnect', async () => {
    const mockGetPendingMessages = apiService.getPendingMessages as jest.Mock;
    mockGetPendingMessages.mockRejectedValueOnce(new Error('API Error'));

    render(
      <ChatProvider>
        <TestComponent />
      </ChatProvider>
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(1);
    });

    const ws = MockWebSocket.instances[0];

    await act(async () => {
      ws.simulateOpen();
    });

    await act(async () => {
      ws.simulateClose();
    });

    await act(async () => {
      jest.advanceTimersByTime(3000);
    });

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBe(2);
    });

    const newWs = MockWebSocket.instances[1];

    await act(async () => {
      newWs.simulateOpen();
    });

    // 即使 API 调用失败，连接也应该正常建立
    await waitFor(() => {
      expect(screen.getByTestId('connected')).toHaveTextContent('connected');
    });
  });
});
