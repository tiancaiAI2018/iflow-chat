import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Chat from './Chat';
import Message from './Message';
import MessageInput from './MessageInput';
import { useAuth } from '../../hooks/useAuth';
import { useChat } from '../../hooks/useWebSocket';

// Mock scrollIntoView
beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

// Mock CSS imports
jest.mock('./Chat.css', () => ({}));
jest.mock('highlight.js/styles/github-dark.css', () => ({}));

// Mock marked module - return proper HTML
jest.mock('marked', () => ({
  marked: {
    setOptions: jest.fn(),
    parse: jest.fn((content: string) => {
      // Simple markdown to HTML conversion for tests
      let html = content;
      // Convert headers
      html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
      html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
      html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
      // Convert bold
      html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      // Convert italic
      html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
      // Convert code blocks
      html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
      // Convert inline code
      html = html.replace(/`(.+?)`/g, '<code>$1</code>');
      // Wrap in paragraph if no block elements
      if (!html.includes('<h1>') && !html.includes('<pre>') && !html.includes('<p>')) {
        html = `<p>${html}</p>`;
      }
      return html;
    }),
  },
}));

// Mock highlight.js
jest.mock('highlight.js', () => ({
  default: {
    getLanguage: jest.fn(() => true),
    highlight: jest.fn((code: string) => ({ value: code })),
    highlightAuto: jest.fn((code: string) => ({ value: code })),
  },
  getLanguage: jest.fn(() => true),
  highlight: jest.fn((code: string) => ({ value: code })),
  highlightAuto: jest.fn((code: string) => ({ value: code })),
}));

// Mock hooks
jest.mock('../../hooks/useAuth');
jest.mock('../../hooks/useWebSocket');
jest.mock('../../services/api', () => ({
  apiService: {
    getWebSocketUrl: jest.fn(() => 'ws://localhost:8000/ws/1?token=test'),
    getChatHistory: jest.fn(() => Promise.resolve({ messages: [], total: 0 })),
    clearChatHistory: jest.fn(() => Promise.resolve({ success: true })),
  },
}));

const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
const mockUseChat = useChat as jest.MockedFunction<typeof useChat>;

// Wrapper component for tests
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>{children}</BrowserRouter>
);

describe('Chat Component', () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({
      user: { id: 1, username: 'test', email: 'test@test.com', created_at: '', last_login: null },
      token: 'test-token',
      isAuthenticated: true,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
      checkAuth: jest.fn(),
    });

    mockUseChat.mockReturnValue({
      messages: [],
      isStreaming: false,
      isWaiting: false,
      isConnected: true,
      error: null,
      sendMessage: jest.fn(),
      clearMessages: jest.fn(),
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders chat container with connection status', async () => {
    await act(async () => {
      render(
        <TestWrapper>
          <Chat />
        </TestWrapper>
      );
    });
    expect(screen.getByText('已连接')).toBeInTheDocument();
  });

  test('shows disconnected status when not connected', async () => {
    mockUseChat.mockReturnValue({
      messages: [],
      isStreaming: false,
      isWaiting: false,
      isConnected: false,
      error: null,
      sendMessage: jest.fn(),
      clearMessages: jest.fn(),
    });

    await act(async () => {
      render(
        <TestWrapper>
          <Chat />
        </TestWrapper>
      );
    });
    expect(screen.getByText('连接中...')).toBeInTheDocument();
  });

  test('disables input when not connected', async () => {
    mockUseChat.mockReturnValue({
      messages: [],
      isStreaming: false,
      isWaiting: false,
      isConnected: false,
      error: null,
      sendMessage: jest.fn(),
      clearMessages: jest.fn(),
    });

    await act(async () => {
      render(
        <TestWrapper>
          <Chat />
        </TestWrapper>
      );
    });
    expect(screen.getByPlaceholderText('输入消息，按 Enter 发送...')).toBeDisabled();
  });

  test('shows empty chat message when no messages', async () => {
    await act(async () => {
      render(
        <TestWrapper>
          <Chat />
        </TestWrapper>
      );
    });
    // Wait for loading to complete
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 100));
    });
    expect(screen.getByText('开始和 iFlow 对话吧！')).toBeInTheDocument();
  });
});

describe('Message Component', () => {
  test('renders user message with correct class', () => {
    const { container } = render(
      <Message
        id="msg-1"
        role="user"
        content="Hello"
        created_at="2024-01-01T00:00:00Z"
      />
    );
    expect(container.querySelector('.message-user')).toBeInTheDocument();
    expect(container.querySelector('.message-avatar')?.textContent).toBe('👤');
  });

  test('renders assistant message with correct class', () => {
    const { container } = render(
      <Message
        id="msg-2"
        role="assistant"
        content="Hi there!"
        created_at="2024-01-01T00:00:00Z"
      />
    );
    expect(container.querySelector('.message-assistant')).toBeInTheDocument();
    expect(container.querySelector('.message-avatar')?.textContent).toBe('🤖');
  });

  test('renders streaming message with cursor', () => {
    const { container } = render(
      <Message
        id="msg-3"
        role="assistant"
        content="Loading..."
        isStreaming={true}
        created_at="2024-01-01T00:00:00Z"
      />
    );
    expect(container.querySelector('.message-cursor')).toBeInTheDocument();
    expect(screen.getByText('▊')).toBeInTheDocument();
  });

  test('renders markdown content as HTML', () => {
    const { container } = render(
      <Message
        id="msg-4"
        role="assistant"
        content="# Title"
        created_at="2024-01-01T00:00:00Z"
      />
    );
    // Check that marked.parse was called and returned HTML
    expect(container.querySelector('.message-text')).toBeInTheDocument();
  });

  test('renders tool calls', () => {
    render(
      <Message
        id="msg-5"
        role="assistant"
        content=""
        toolCalls={[
          {
            tool_name: 'get_weather',
            arguments: { city: 'Beijing' },
            status: 'completed',
            result: 'Sunny',
          },
        ]}
        created_at="2024-01-01T00:00:00Z"
      />
    );
    expect(screen.getByText('get_weather')).toBeInTheDocument();
    expect(screen.getByText('✅')).toBeInTheDocument();
  });

  test('renders pending tool call', () => {
    render(
      <Message
        id="msg-6"
        role="assistant"
        content=""
        toolCalls={[
          {
            tool_name: 'search',
            arguments: { query: 'test' },
            status: 'pending',
          },
        ]}
        created_at="2024-01-01T00:00:00Z"
      />
    );
    expect(screen.getByText('search')).toBeInTheDocument();
    expect(screen.getByText('⏳')).toBeInTheDocument();
  });
});

describe('MessageInput Component', () => {
  test('renders input field', () => {
    render(<MessageInput onSend={jest.fn()} />);
    expect(screen.getByPlaceholderText('输入消息...')).toBeInTheDocument();
  });

  test('sends message on button click', () => {
    const mockOnSend = jest.fn();
    render(<MessageInput onSend={mockOnSend} />);

    const input = screen.getByPlaceholderText('输入消息...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    
    const sendButton = screen.getByText('发送');
    fireEvent.click(sendButton);

    expect(mockOnSend).toHaveBeenCalledWith('Test message');
  });

  test('sends message on Enter key', () => {
    const mockOnSend = jest.fn();
    render(<MessageInput onSend={mockOnSend} />);

    const input = screen.getByPlaceholderText('输入消息...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(mockOnSend).toHaveBeenCalledWith('Test message');
  });

  test('does not send empty message', () => {
    const mockOnSend = jest.fn();
    render(<MessageInput onSend={mockOnSend} />);

    const sendButton = screen.getByText('发送');
    fireEvent.click(sendButton);

    expect(mockOnSend).not.toHaveBeenCalled();
  });

  test('input is disabled when prop is true', () => {
    render(<MessageInput onSend={jest.fn()} disabled={true} />);
    expect(screen.getByPlaceholderText('输入消息...')).toBeDisabled();
  });

  test('send button is disabled when input is empty', () => {
    render(<MessageInput onSend={jest.fn()} />);
    expect(screen.getByText('发送')).toBeDisabled();
  });

  test('send button is disabled when disabled prop is true', () => {
    render(<MessageInput onSend={jest.fn()} disabled={true} />);
    const input = screen.getByPlaceholderText('输入消息...');
    fireEvent.change(input, { target: { value: 'Test' } });
    expect(screen.getByText('发送')).toBeDisabled();
  });

  test('uses custom placeholder', () => {
    render(<MessageInput onSend={jest.fn()} placeholder="Type here..." />);
    expect(screen.getByPlaceholderText('Type here...')).toBeInTheDocument();
  });

  test('clears input after sending', () => {
    const mockOnSend = jest.fn();
    render(<MessageInput onSend={mockOnSend} />);

    const input = screen.getByPlaceholderText('输入消息...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(input).toHaveValue('');
  });

  test('shift+enter does not send message', () => {
    const mockOnSend = jest.fn();
    render(<MessageInput onSend={mockOnSend} />);

    const input = screen.getByPlaceholderText('输入消息...');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', shiftKey: true });

    expect(mockOnSend).not.toHaveBeenCalled();
  });
});
