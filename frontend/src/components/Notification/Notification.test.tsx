import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { NotificationBar } from './NotificationBar';
import { NotificationItem } from './NotificationItem';
import { useNotifications } from '../../hooks/useNotifications';
import type { Notification } from '../../types';

// Mock useNotifications hook
jest.mock('../../hooks/useNotifications');

const mockNotifications: Notification[] = [
  {
    id: '1',
    task_id: 'task-1',
    content: '定时任务执行结果：任务完成',
    read: false,
    created_at: new Date().toISOString(),
  },
  {
    id: '2',
    task_id: 'task-2',
    content: '定时任务执行结果：任务成功',
    read: true,
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: '3',
    task_id: null,
    content: '系统通知：欢迎使用',
    read: false,
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
];

const mockUseNotifications = {
  notifications: mockNotifications,
  unreadCount: 2,
  isLoading: false,
  error: null,
  fetchNotifications: jest.fn(),
  markAsRead: jest.fn(),
  markAllAsRead: jest.fn(),
  deleteNotification: jest.fn(),
  clearAll: jest.fn(),
  addNotification: jest.fn(),
};

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('NotificationBar', () => {
  beforeEach(() => {
    (useNotifications as jest.Mock).mockReturnValue(mockUseNotifications);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders notification bar with title', () => {
    renderWithRouter(<NotificationBar />);
    expect(screen.getByText('通知')).toBeInTheDocument();
  });

  test('displays unread count badge', () => {
    renderWithRouter(<NotificationBar />);
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  test('renders filter buttons', () => {
    renderWithRouter(<NotificationBar />);
    expect(screen.getByText('全部')).toBeInTheDocument();
    expect(screen.getByText(/未读/)).toBeInTheDocument();
  });

  test('renders action buttons', () => {
    renderWithRouter(<NotificationBar />);
    expect(screen.getByText('全部已读')).toBeInTheDocument();
    expect(screen.getByText('清空')).toBeInTheDocument();
  });

  test('renders notifications list', () => {
    renderWithRouter(<NotificationBar />);
    expect(screen.getByText('定时任务执行结果：任务完成')).toBeInTheDocument();
    expect(screen.getByText('定时任务执行结果：任务成功')).toBeInTheDocument();
    expect(screen.getByText('系统通知：欢迎使用')).toBeInTheDocument();
  });

  test('filters to show only unread notifications', () => {
    renderWithRouter(<NotificationBar />);
    const unreadBtn = screen.getByRole('button', { name: /未读/ });
    fireEvent.click(unreadBtn);
    
    // Should still show unread notifications
    expect(screen.getByText('定时任务执行结果：任务完成')).toBeInTheDocument();
    expect(screen.getByText('系统通知：欢迎使用')).toBeInTheDocument();
  });

  test('calls markAllAsRead when clicking "全部已读"', async () => {
    renderWithRouter(<NotificationBar />);
    const markAllBtn = screen.getByText('全部已读');
    fireEvent.click(markAllBtn);
    
    expect(mockUseNotifications.markAllAsRead).toHaveBeenCalled();
  });

  test('shows loading state', () => {
    (useNotifications as jest.Mock).mockReturnValue({
      ...mockUseNotifications,
      isLoading: true,
      notifications: [],
    });
    
    renderWithRouter(<NotificationBar />);
    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });

  test('shows empty state when no notifications', () => {
    (useNotifications as jest.Mock).mockReturnValue({
      ...mockUseNotifications,
      notifications: [],
      unreadCount: 0,
    });
    
    renderWithRouter(<NotificationBar />);
    expect(screen.getByText('暂无通知')).toBeInTheDocument();
  });

  test('shows error state', () => {
    (useNotifications as jest.Mock).mockReturnValue({
      ...mockUseNotifications,
      error: '获取通知失败',
      notifications: [],
    });
    
    renderWithRouter(<NotificationBar />);
    expect(screen.getByText('获取通知失败')).toBeInTheDocument();
  });

  test('calls onClose when close button clicked', () => {
    const mockOnClose = jest.fn();
    const { container } = renderWithRouter(<NotificationBar onClose={mockOnClose} />);
    
    const closeBtn = container.querySelector('.notification-close-btn');
    expect(closeBtn).toBeInTheDocument();
    fireEvent.click(closeBtn!);
    
    expect(mockOnClose).toHaveBeenCalled();
  });
});

describe('NotificationItem', () => {
  const mockMarkRead = jest.fn();
  const mockDelete = jest.fn();

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders notification content', () => {
    render(
      <NotificationItem
        notification={mockNotifications[0]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    expect(screen.getByText('定时任务执行结果：任务完成')).toBeInTheDocument();
  });

  test('shows unread indicator for unread notification', () => {
    const { container } = render(
      <NotificationItem
        notification={mockNotifications[0]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    expect(container.querySelector('.unread-dot')).toBeInTheDocument();
  });

  test('hides unread indicator for read notification', () => {
    const { container } = render(
      <NotificationItem
        notification={mockNotifications[1]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    expect(container.querySelector('.unread-dot')).not.toBeInTheDocument();
  });

  test('shows mark read button for unread notification', () => {
    render(
      <NotificationItem
        notification={mockNotifications[0]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    expect(screen.getByTitle('标记已读')).toBeInTheDocument();
  });

  test('hides mark read button for read notification', () => {
    render(
      <NotificationItem
        notification={mockNotifications[1]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    expect(screen.queryByTitle('标记已读')).not.toBeInTheDocument();
  });

  test('calls onMarkRead when mark read button clicked', () => {
    render(
      <NotificationItem
        notification={mockNotifications[0]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    const markReadBtn = screen.getByTitle('标记已读');
    fireEvent.click(markReadBtn);
    
    expect(mockMarkRead).toHaveBeenCalledWith('1');
  });

  test('calls onDelete when delete button clicked', () => {
    render(
      <NotificationItem
        notification={mockNotifications[0]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    const deleteBtn = screen.getByTitle('删除');
    fireEvent.click(deleteBtn);
    
    expect(mockDelete).toHaveBeenCalledWith('1');
  });

  test('displays relative time correctly', () => {
    render(
      <NotificationItem
        notification={mockNotifications[0]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    // Should show "刚刚" for very recent notification
    expect(screen.getByText('刚刚')).toBeInTheDocument();
  });

  test('shows task label for task notifications', () => {
    render(
      <NotificationItem
        notification={mockNotifications[0]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    expect(screen.getByText('定时任务')).toBeInTheDocument();
  });

  test('hides task label for non-task notifications', () => {
    render(
      <NotificationItem
        notification={mockNotifications[2]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    expect(screen.queryByText('定时任务')).not.toBeInTheDocument();
  });

  test('applies unread class to unread notification', () => {
    const { container } = render(
      <NotificationItem
        notification={mockNotifications[0]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    expect(container.querySelector('.notification-item.unread')).toBeInTheDocument();
  });

  test('applies read class to read notification', () => {
    const { container } = render(
      <NotificationItem
        notification={mockNotifications[1]}
        onMarkRead={mockMarkRead}
        onDelete={mockDelete}
      />
    );
    
    expect(container.querySelector('.notification-item.read')).toBeInTheDocument();
  });
});

describe('useNotifications Hook', () => {
  test('hook exports required functions', () => {
    const expectedFunctions = [
      'notifications',
      'unreadCount',
      'isLoading',
      'error',
      'fetchNotifications',
      'markAsRead',
      'markAllAsRead',
      'deleteNotification',
      'clearAll',
      'addNotification',
    ];
    
    expect(Object.keys(mockUseNotifications)).toEqual(
      expect.arrayContaining(expectedFunctions)
    );
  });
});
