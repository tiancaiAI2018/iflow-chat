import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import NewChatButton from './NewChatButton';

// Mock CSS import
jest.mock('./NewChatButton.css', () => ({}));

// Mock ChatContext
const mockCreateNewConversation = jest.fn();

jest.mock('../../contexts/ChatContext', () => ({
  useChatContext: () => ({
    createNewConversation: mockCreateNewConversation,
    isStreaming: false,
  }),
}));

describe('NewChatButton Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders button with + icon and text', () => {
    render(<NewChatButton />);
    expect(screen.getByText('+')).toBeInTheDocument();
    expect(screen.getByText('新对话')).toBeInTheDocument();
  });

  test('has correct title attribute', () => {
    render(<NewChatButton />);
    expect(screen.getByTitle('新建对话')).toBeInTheDocument();
  });

  test('has correct aria-label', () => {
    render(<NewChatButton />);
    expect(screen.getByLabelText('新建对话')).toBeInTheDocument();
  });

  test('calls createNewConversation when clicked', async () => {
    mockCreateNewConversation.mockResolvedValue({ id: 1, title: 'New Chat' });
    
    render(<NewChatButton />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);
    
    expect(mockCreateNewConversation).toHaveBeenCalledTimes(1);
  });

  test('is disabled when isStreaming is true', () => {
    jest.resetModules();
    jest.doMock('../../contexts/ChatContext', () => ({
      useChatContext: () => ({
        createNewConversation: mockCreateNewConversation,
        isStreaming: true,
      }),
    }));

    // Need to re-import after changing mock
    const NewChatButtonStreaming = require('./NewChatButton').default;
    
    render(<NewChatButtonStreaming />);
    
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  test('does not call createNewConversation when streaming', () => {
    jest.resetModules();
    jest.doMock('../../contexts/ChatContext', () => ({
      useChatContext: () => ({
        createNewConversation: mockCreateNewConversation,
        isStreaming: true,
      }),
    }));

    const NewChatButtonStreaming = require('./NewChatButton').default;
    
    render(<NewChatButtonStreaming />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);
    
    expect(mockCreateNewConversation).not.toHaveBeenCalled();
  });

  test('accepts custom className', () => {
    render(<NewChatButton className="custom-class" />);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('new-chat-button');
    expect(button).toHaveClass('custom-class');
  });

  test('button has correct base class', () => {
    render(<NewChatButton />);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('new-chat-button');
  });

  test('icon has correct class', () => {
    const { container } = render(<NewChatButton />);
    const icon = container.querySelector('.new-chat-icon');
    expect(icon).toBeInTheDocument();
  });

  test('text has correct class', () => {
    const { container } = render(<NewChatButton />);
    const text = container.querySelector('.new-chat-text');
    expect(text).toBeInTheDocument();
  });

  test('handles async createNewConversation', async () => {
    mockCreateNewConversation.mockResolvedValue({ 
      id: 2, 
      title: 'Test Conversation' 
    });
    
    render(<NewChatButton />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);
    
    // Wait for async operation
    await screen.findByRole('button');
    
    expect(mockCreateNewConversation).toHaveBeenCalled();
  });

  test('handles createNewConversation rejection gracefully', async () => {
    // Mock console.error before the test
    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
    
    // Set up the mock to reject
    mockCreateNewConversation.mockRejectedValueOnce(new Error('Network error'));
    
    render(<NewChatButton />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);
    
    // Wait for async operation to complete
    await screen.findByRole('button');
    
    expect(mockCreateNewConversation).toHaveBeenCalled();
    // Component should handle the error gracefully (log it)
    expect(consoleError).toHaveBeenCalledWith('Failed to create conversation:', expect.any(Error));
    
    consoleError.mockRestore();
  });

  test('button type is button (not submit)', () => {
    render(<NewChatButton />);
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('type', 'button');
  });
});
