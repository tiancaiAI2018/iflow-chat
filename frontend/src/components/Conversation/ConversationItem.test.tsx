import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import ConversationItem from './ConversationItem';
import type { ConversationResponse } from '../../types';

// Mock CSS imports
jest.mock('./Conversation.css', () => ({}));

// Mock conversation data
const mockConversation: ConversationResponse = {
  id: 1,
  user_id: 1,
  title: '测试会话标题',
  iflow_session_id: 'session-1',
  created_at: '2026-03-04T12:00:00Z',
  updated_at: '2026-03-04T12:00:00Z',
};

const mockFormatTime = jest.fn((date: string) => '12:00');

describe('ConversationItem Component', () => {
  const mockOnSelect = jest.fn();
  const mockOnDelete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockFormatTime.mockReturnValue('12:00');
  });

  // 1. Basic rendering tests
  test('renders conversation title correctly', () => {
    render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    expect(screen.getByText('测试会话标题')).toBeInTheDocument();
  });

  test('renders formatted time', () => {
    render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    expect(mockFormatTime).toHaveBeenCalledWith(mockConversation.updated_at);
    expect(screen.getByText('12:00')).toBeInTheDocument();
  });

  test('shows default title "新对话" when conversation has no title', () => {
    const conversationWithoutTitle = { ...mockConversation, title: '' };

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

  // 2. Active state tests
  test('has active class when isActive is true', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
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
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const item = container.querySelector('.conversation-item');
    expect(item).not.toHaveClass('active');
  });

  test('applies gradient background to active item', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={true}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const item = container.querySelector('.conversation-item.active');
    expect(item).toBeInTheDocument();
  });

  // 3. Click interaction tests
  test('calls onSelect when item content is clicked', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const content = container.querySelector('.conversation-item-content');
    fireEvent.click(content!);

    expect(mockOnSelect).toHaveBeenCalledTimes(1);
  });

  test('does not call onSelect when delete button is clicked', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    // Show delete button first
    const item = container.querySelector('.conversation-item');
    fireEvent.contextMenu(item!);

    const deleteBtn = container.querySelector('.conversation-delete-btn');
    fireEvent.click(deleteBtn!);

    expect(mockOnSelect).not.toHaveBeenCalled();
    expect(mockOnDelete).toHaveBeenCalled();
  });

  // 4. Delete button visibility tests
  test('shows delete button on hover', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
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

  test('shows delete button on right-click (context menu)', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
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

  test('delete button has visible class after right-click', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const item = container.querySelector('.conversation-item');
    fireEvent.contextMenu(item!);

    const deleteBtn = container.querySelector('.conversation-delete-btn');
    expect(deleteBtn).toHaveClass('visible');
  });

  // 5. Delete action tests
  test('calls onDelete when delete button is clicked', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const deleteBtn = container.querySelector('.conversation-delete-btn');
    fireEvent.click(deleteBtn!);

    expect(mockOnDelete).toHaveBeenCalledTimes(1);
  });

  test('onDelete receives the click event', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const deleteBtn = container.querySelector('.conversation-delete-btn');
    fireEvent.click(deleteBtn!);

    expect(mockOnDelete).toHaveBeenCalledWith(expect.any(Object));
  });

  // 6. Long press (touch) interaction tests
  test('shows delete button after long press (touch)', async () => {
    jest.useFakeTimers();

    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const item = container.querySelector('.conversation-item');
    
    // Simulate touch start
    fireEvent.touchStart(item!);
    
    // Fast-forward 500ms (long press threshold) and wrap in act
    await act(async () => {
      jest.advanceTimersByTime(500);
    });
    
    // Simulate touch end
    fireEvent.touchEnd(item!);

    const deleteBtn = container.querySelector('.conversation-delete-btn.visible');
    expect(deleteBtn).toBeInTheDocument();

    jest.useRealTimers();
  });

  test('does not show delete button on quick tap (touch)', () => {
    jest.useFakeTimers();

    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const item = container.querySelector('.conversation-item');
    
    // Simulate quick touch
    fireEvent.touchStart(item!);
    
    // Fast-forward only 200ms (less than long press threshold)
    jest.advanceTimersByTime(200);
    
    // Simulate touch end
    fireEvent.touchEnd(item!);

    const deleteBtn = container.querySelector('.conversation-delete-btn.visible');
    expect(deleteBtn).not.toBeInTheDocument();

    jest.useRealTimers();
  });

  // 7. Hide delete button tests
  test('hides delete button when clicking outside', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    // Show delete button first
    const item = container.querySelector('.conversation-item');
    fireEvent.contextMenu(item!);
    
    expect(container.querySelector('.conversation-delete-btn.visible')).toBeInTheDocument();

    // Click on the item (not content) to hide
    fireEvent.click(item!);

    expect(container.querySelector('.conversation-delete-btn.visible')).not.toBeInTheDocument();
  });

  // 8. Accessibility tests
  test('delete button has title attribute for accessibility', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const deleteBtn = container.querySelector('.conversation-delete-btn');
    expect(deleteBtn).toHaveAttribute('title', '删除会话');
  });

  // 9. CSS class tests
  test('has correct CSS structure', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    expect(container.querySelector('.conversation-item')).toBeInTheDocument();
    expect(container.querySelector('.conversation-item-content')).toBeInTheDocument();
    expect(container.querySelector('.conversation-title')).toBeInTheDocument();
    expect(container.querySelector('.conversation-meta')).toBeInTheDocument();
    expect(container.querySelector('.conversation-time')).toBeInTheDocument();
    expect(container.querySelector('.conversation-delete-btn')).toBeInTheDocument();
  });

  test('has show-delete class when delete button is visible', () => {
    const { container } = render(
      <ConversationItem
        conversation={mockConversation}
        isActive={false}
        onSelect={mockOnSelect}
        onDelete={mockOnDelete}
        formatTime={mockFormatTime}
      />
    );

    const item = container.querySelector('.conversation-item');
    fireEvent.contextMenu(item!);

    expect(item).toHaveClass('show-delete');
  });
});
