import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import ConversationDrawer from './ConversationDrawer';
import ConversationItem from './ConversationItem';
import { useChatContext } from '../../contexts/ChatContext';

// Mock CSS imports
jest.mock('./Conversation.css', () => ({}));

// Mock ChatContext
jest.mock('../../contexts/ChatContext');

const mockUseChatContext = useChatContext as jest.MockedFunction<typeof useChatContext>;

// Mock conversation data
const mockConversations = [
  {
    id: 1,
    user_id: 1,
    title: '今天的话题',
    iflow_session_id: 'session-1',
    working_directory: '/root/.iflow-bot/workspace',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 2,
    user_id: 1,
    title: '昨天的话题',
    iflow_session_id: 'session-2',
    working_directory: '/root/.iflow-bot/workspace',
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: 3,
    user_id: 1,
    title: '更早的话题',
    iflow_session_id: 'session-3',
    working_directory: '/root/.iflow-bot/workspace',
    created_at: new Date(Date.now() - 7 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 7 * 86400000).toISOString(),
  },
];

describe('ConversationDrawer Component', () => {
  const mockOnClose = jest.fn();
  const mockLoadConversations = jest.fn();
  const mockSwitchConversation = jest.fn();
  const mockDeleteConversation = jest.fn();
  const mockCreateNewConversation = jest.fn();
  const mockOpenWorkspaceModal = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseChatContext.mockReturnValue({
      messages: [],
      isStreaming: false,
      isWaiting: false,
      isConnected: true,
      error: null,
      sendMessage: jest.fn(),
      clearMessages: jest.fn(),
      conversations: mockConversations,
      currentConversationId: 1,
      currentConversation: mockConversations[0],
      isLoadingConversations: false,
      loadConversations: mockLoadConversations,
      switchConversation: mockSwitchConversation,
      createNewConversation: mockCreateNewConversation,
      deleteConversation: mockDeleteConversation,
      // 工作目录选择相关
      showWorkspaceModal: false,
      isCreatingConversation: false,
      openWorkspaceModal: mockOpenWorkspaceModal,
      closeWorkspaceModal: jest.fn(),
      createNewConversationWithWorkspace: jest.fn(),
    });
  });

  test('renders drawer with correct title', () => {
    render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    expect(screen.getByText('历史会话')).toBeInTheDocument();
  });

  test('renders new chat button', () => {
    render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    expect(screen.getByText('新对话')).toBeInTheDocument();
  });

  test('calls loadConversations when drawer opens', () => {
    render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    expect(mockLoadConversations).toHaveBeenCalled();
  });

  test('shows loading state', () => {
    mockUseChatContext.mockReturnValue({
      ...mockUseChatContext(),
      isLoadingConversations: true,
      conversations: [],
    });

    render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });

  test('shows empty state when no conversations', () => {
    mockUseChatContext.mockReturnValue({
      ...mockUseChatContext(),
      conversations: [],
      currentConversation: null,
    });

    render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    expect(screen.getByText('暂无会话记录')).toBeInTheDocument();
    expect(screen.getByText('开始新对话')).toBeInTheDocument();
  });

  test('renders conversation list grouped by date', () => {
    render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    
    expect(screen.getByText('今天的话题')).toBeInTheDocument();
    expect(screen.getByText('昨天的话题')).toBeInTheDocument();
    expect(screen.getByText('更早的话题')).toBeInTheDocument();
  });

  test('shows group labels', () => {
    const { container } = render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    
    // Use container.querySelector to find group labels specifically
    const groupLabels = container.querySelectorAll('.group-label');
    const labelTexts = Array.from(groupLabels).map(el => el.textContent);
    
    expect(labelTexts).toContain('今天');
    expect(labelTexts).toContain('昨天');
    expect(labelTexts).toContain('更早');
  });

  test('highlights active conversation', () => {
    const { container } = render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    
    const activeItem = container.querySelector('.conversation-item.active');
    expect(activeItem).toBeInTheDocument();
    expect(activeItem?.textContent).toContain('今天的话题');
  });

  test('calls onClose when overlay is clicked', () => {
    const { container } = render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    
    const overlay = container.querySelector('.conversation-drawer-overlay');
    fireEvent.click(overlay!);
    
    expect(mockOnClose).toHaveBeenCalled();
  });

  test('calls createNewConversation when new chat button is clicked', async () => {
    mockCreateNewConversation.mockResolvedValueOnce(mockConversations[0]);

    render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    
    const newChatButton = screen.getByText('新对话').closest('button')!;
    await act(async () => {
      fireEvent.click(newChatButton);
    });

    expect(mockCreateNewConversation).toHaveBeenCalled();
    expect(mockOnClose).toHaveBeenCalled();
  });

  test('drawer has open class when isOpen is true', () => {
    const { container } = render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    
    const drawer = container.querySelector('.conversation-drawer');
    expect(drawer).toHaveClass('open');
  });

  test('drawer does not have open class when isOpen is false', () => {
    const { container } = render(<ConversationDrawer isOpen={false} onClose={mockOnClose} />);
    
    const drawer = container.querySelector('.conversation-drawer');
    expect(drawer).not.toHaveClass('open');
  });

  test('overlay has open class when isOpen is true', () => {
    const { container } = render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    
    const overlay = container.querySelector('.conversation-drawer-overlay');
    expect(overlay).toHaveClass('open');
  });
});

describe('ConversationItem Component', () => {
  const mockOnSelect = jest.fn();
  const mockOnDelete = jest.fn();
  const mockFormatTime = jest.fn((date: string) => '12:00');

  const conversation = mockConversations[0];

  beforeEach(() => {
    jest.clearAllMocks();
    mockFormatTime.mockReturnValue('12:00');
  });

  test('renders conversation title', () => {
    render(
      <ConversationItem
        conversation={conversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    expect(screen.getByText('今天的话题')).toBeInTheDocument();
  });

  test('renders formatted time', () => {
    render(
      <ConversationItem
        conversation={conversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    expect(mockFormatTime).toHaveBeenCalledWith(conversation.updated_at);
  });

  test('has active class when isActive is true', () => {
    const { container } = render(
      <ConversationItem
        conversation={conversation}
        isActive={true}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const item = container.querySelector('.conversation-item');
    expect(item).toHaveClass('active');
  });

  test('does not have active class when isActive is false', () => {
    const { container } = render(
      <ConversationItem
        conversation={conversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const item = container.querySelector('.conversation-item');
    expect(item).not.toHaveClass('active');
  });

  test('calls onSelect when item content is clicked', () => {
    const { container } = render(
      <ConversationItem
        conversation={conversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const content = container.querySelector('.conversation-item-content');
    fireEvent.click(content!);

    expect(mockOnSelect).toHaveBeenCalled();
  });

  test('shows delete button on hover', () => {
    const { container } = render(
      <ConversationItem
        conversation={conversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const item = container.querySelector('.conversation-item');
    fireEvent.mouseEnter(item!);

    const deleteBtn = container.querySelector('.conversation-delete-btn');
    expect(deleteBtn).toBeInTheDocument();
  });

  test('calls onDelete when delete button is clicked', () => {
    window.confirm = jest.fn(() => true);

    const { container } = render(
      <ConversationItem
        conversation={conversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const deleteBtn = container.querySelector('.conversation-delete-btn');
    fireEvent.click(deleteBtn!);

    expect(mockOnDelete).toHaveBeenCalled();
  });

  test('shows delete button on right-click', () => {
    const { container } = render(
      <ConversationItem
        conversation={conversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const item = container.querySelector('.conversation-item');
    fireEvent.contextMenu(item!);

    const deleteBtn = container.querySelector('.conversation-delete-btn.visible');
    expect(deleteBtn).toBeInTheDocument();
  });

  test('shows default title when conversation has no title', () => {
    const conversationWithoutTitle = { ...conversation, title: '' };

    render(
      <ConversationItem
        conversation={conversationWithoutTitle}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    expect(screen.getByText('新对话')).toBeInTheDocument();
  });
});

describe('ConversationDrawer Touch Interactions', () => {
  const mockOnClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseChatContext.mockReturnValue({
      messages: [],
      isStreaming: false,
      isWaiting: false,
      isConnected: true,
      error: null,
      sendMessage: jest.fn(),
      clearMessages: jest.fn(),
      conversations: mockConversations,
      currentConversationId: 1,
      currentConversation: mockConversations[0],
      isLoadingConversations: false,
      loadConversations: jest.fn(),
      switchConversation: jest.fn(),
      createNewConversation: jest.fn(),
      deleteConversation: jest.fn(),
      // 工作目录选择相关
      showWorkspaceModal: false,
      isCreatingConversation: false,
      openWorkspaceModal: jest.fn(),
      closeWorkspaceModal: jest.fn(),
      createNewConversationWithWorkspace: jest.fn(),
    });
  });

  test('handles touch swipe to close', async () => {
    const { container } = render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    
    const drawer = container.querySelector('.conversation-drawer')!;
    
    // Simulate touch swipe left
    fireEvent.touchStart(drawer, { touches: [{ clientX: 200, clientY: 100 }] });
    fireEvent.touchMove(drawer, { touches: [{ clientX: 50, clientY: 100 }] });
    fireEvent.touchEnd(drawer);

    expect(mockOnClose).toHaveBeenCalled();
  });

  test('does not close on small swipe', () => {
    const { container } = render(<ConversationDrawer isOpen={true} onClose={mockOnClose} />);
    
    const drawer = container.querySelector('.conversation-drawer')!;
    
    // Simulate small touch swipe
    fireEvent.touchStart(drawer, { touches: [{ clientX: 200, clientY: 100 }] });
    fireEvent.touchMove(drawer, { touches: [{ clientX: 180, clientY: 100 }] });
    fireEvent.touchEnd(drawer);

    expect(mockOnClose).not.toHaveBeenCalled();
  });
});
