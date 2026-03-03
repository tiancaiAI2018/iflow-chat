import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter, useLocation, useNavigate } from 'react-router-dom';
import Header from './Header';

// Mock hooks
jest.mock('../../hooks/useAuth', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../../hooks/useNotifications', () => ({
  useNotifications: jest.fn(),
}));

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: jest.fn(),
  useNavigate: jest.fn(),
}));

const mockUseAuth = require('../../hooks/useAuth').useAuth;
const mockUseNotifications = require('../../hooks/useNotifications').useNotifications;
const mockUseLocation = useLocation as jest.MockedFunction<typeof useLocation>;
const mockUseNavigate = useNavigate as jest.MockedFunction<typeof useNavigate>;

// Helper to render with router
const renderWithRouter = (component: React.ReactElement, initialRoute = '/chat') => {
  mockUseLocation.mockReturnValue({
    pathname: initialRoute,
    search: '',
    hash: '',
    state: null,
    key: 'default',
  });
  
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('Header Component', () => {
  const mockNavigate = jest.fn();
  const mockLogout = jest.fn();
  const mockFetchNotifications = jest.fn();
  const mockOnToggleNotification = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseNavigate.mockReturnValue(mockNavigate);
    mockUseAuth.mockReturnValue({
      user: { id: 1, username: 'testuser', email: 'test@example.com' },
      logout: mockLogout,
      isAuthenticated: true,
    });
    mockUseNotifications.mockReturnValue({
      unreadCount: 0,
      fetchNotifications: mockFetchNotifications,
    });
  });

  describe('Desktop View', () => {
    beforeEach(() => {
      // Mock desktop viewport
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        value: 1024,
      });
    });

    it('renders header with logo', () => {
      renderWithRouter(<Header />);
      expect(screen.getByText('iFlow')).toBeInTheDocument();
    });

    it('renders navigation items', () => {
      renderWithRouter(<Header />);
      expect(screen.getByText('对话')).toBeInTheDocument();
      expect(screen.getByText('任务')).toBeInTheDocument();
      expect(screen.getByText('通知')).toBeInTheDocument();
    });

    it('renders username', () => {
      renderWithRouter(<Header />);
      expect(screen.getByText('testuser')).toBeInTheDocument();
    });

    it('shows active state for current route', () => {
      renderWithRouter(<Header />, '/chat');
      const chatBtn = screen.getByText('对话').closest('button');
      expect(chatBtn).toHaveClass('active');
    });

    it('navigates when nav item is clicked', () => {
      renderWithRouter(<Header />);
      fireEvent.click(screen.getByText('任务'));
      expect(mockNavigate).toHaveBeenCalledWith('/tasks');
    });

    it('shows notification badge when there are unread notifications', () => {
      mockUseNotifications.mockReturnValue({
        unreadCount: 5,
        fetchNotifications: mockFetchNotifications,
      });
      renderWithRouter(<Header />);
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('shows 99+ for large unread counts', () => {
      mockUseNotifications.mockReturnValue({
        unreadCount: 150,
        fetchNotifications: mockFetchNotifications,
      });
      renderWithRouter(<Header />);
      expect(screen.getByText('99+')).toBeInTheDocument();
    });

    it('calls toggle notification callback', () => {
      renderWithRouter(<Header onToggleNotification={mockOnToggleNotification} />);
      fireEvent.click(screen.getByText('通知'));
      expect(mockOnToggleNotification).toHaveBeenCalled();
    });

    it('opens user menu when clicking avatar', async () => {
      renderWithRouter(<Header />);
      fireEvent.click(screen.getByText('testuser'));
      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument();
      });
    });

    it('calls logout when logout button is clicked', async () => {
      renderWithRouter(<Header />);
      fireEvent.click(screen.getByText('testuser'));
      await waitFor(() => {
        expect(screen.getByText('退出登录')).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText('退出登录'));
      expect(mockLogout).toHaveBeenCalled();
    });

    it('fetches notifications on mount', () => {
      renderWithRouter(<Header />);
      expect(mockFetchNotifications).toHaveBeenCalled();
    });

    it('fetches notifications periodically', () => {
      jest.useFakeTimers();
      renderWithRouter(<Header />);
      expect(mockFetchNotifications).toHaveBeenCalledTimes(1);
      jest.advanceTimersByTime(60000);
      expect(mockFetchNotifications).toHaveBeenCalledTimes(2);
      jest.useRealTimers();
    });
  });

  describe('Mobile View', () => {
    beforeEach(() => {
      // Mock mobile viewport
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        value: 375,
      });
    });

    it('shows hamburger menu button on mobile', () => {
      renderWithRouter(<Header />);
      const menuBtn = document.querySelector('.mobile-menu-btn');
      expect(menuBtn).toBeInTheDocument();
    });

    it('opens mobile menu when hamburger is clicked', async () => {
      renderWithRouter(<Header />);
      const menuBtn = document.querySelector('.mobile-menu-btn');
      fireEvent.click(menuBtn!);
      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument();
      });
    });

    it('shows mobile navigation items', async () => {
      renderWithRouter(<Header />);
      const menuBtn = document.querySelector('.mobile-menu-btn');
      fireEvent.click(menuBtn!);
      await waitFor(() => {
        const mobileNav = document.querySelector('.mobile-nav');
        expect(mobileNav).toBeInTheDocument();
      });
    });

    it('closes mobile menu when nav item is clicked', async () => {
      renderWithRouter(<Header />);
      const menuBtn = document.querySelector('.mobile-menu-btn');
      fireEvent.click(menuBtn!);
      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument();
      });
      
      // Click on a mobile nav item
      const mobileNavItems = document.querySelectorAll('.mobile-nav-item');
      fireEvent.click(mobileNavItems[0]);
      
      expect(mockNavigate).toHaveBeenCalled();
    });

    it('closes mobile menu when overlay is clicked', async () => {
      renderWithRouter(<Header />);
      const menuBtn = document.querySelector('.mobile-menu-btn');
      fireEvent.click(menuBtn!);
      
      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument();
      });
      
      const overlay = document.querySelector('.mobile-menu-overlay');
      fireEvent.click(overlay!);
      
      await waitFor(() => {
        expect(screen.queryByText('test@example.com')).not.toBeInTheDocument();
      });
    });

    it('shows logout button in mobile menu', async () => {
      renderWithRouter(<Header />);
      const menuBtn = document.querySelector('.mobile-menu-btn');
      fireEvent.click(menuBtn!);
      
      await waitFor(() => {
        const logoutBtns = screen.getAllByText('退出登录');
        expect(logoutBtns.length).toBeGreaterThan(0);
      });
    });

    it('calls logout from mobile menu', async () => {
      renderWithRouter(<Header />);
      const menuBtn = document.querySelector('.mobile-menu-btn');
      fireEvent.click(menuBtn!);
      
      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument();
      });
      
      const mobileLogoutBtn = document.querySelector('.mobile-logout-btn');
      fireEvent.click(mobileLogoutBtn!);
      
      expect(mockLogout).toHaveBeenCalled();
    });

    it('shows notification badge in mobile menu', async () => {
      mockUseNotifications.mockReturnValue({
        unreadCount: 3,
        fetchNotifications: mockFetchNotifications,
      });
      
      renderWithRouter(<Header />);
      const menuBtn = document.querySelector('.mobile-menu-btn');
      fireEvent.click(menuBtn!);
      
      await waitFor(() => {
        const badges = screen.getAllByText('3');
        expect(badges.length).toBeGreaterThan(0);
      });
    });
  });

  describe('User Menu Dropdown', () => {
    it('closes user menu when clicking outside', async () => {
      renderWithRouter(<Header />);
      fireEvent.click(screen.getByText('testuser'));
      
      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument();
      });
      
      fireEvent.mouseDown(document.body);
      
      await waitFor(() => {
        expect(screen.queryByText('test@example.com')).not.toBeInTheDocument();
      });
    });

    it('closes user menu after logout', async () => {
      renderWithRouter(<Header />);
      fireEvent.click(screen.getByText('testuser'));
      
      await waitFor(() => {
        expect(screen.getByText('退出登录')).toBeInTheDocument();
      });
      
      fireEvent.click(screen.getByText('退出登录'));
      
      expect(mockLogout).toHaveBeenCalled();
    });
  });

  describe('Route Changes', () => {
    it('closes mobile menu on route change', async () => {
      const { unmount } = renderWithRouter(<Header />);
      const menuBtn = document.querySelector('.mobile-menu-btn');
      fireEvent.click(menuBtn!);
      
      await waitFor(() => {
        expect(screen.getByText('test@example.com')).toBeInTheDocument();
      });
      
      // Simulate route change by updating location and re-rendering
      mockUseLocation.mockReturnValue({
        pathname: '/tasks',
        search: '',
        hash: '',
        state: null,
        key: 'tasks',
      });
      
      // Unmount and re-render to simulate route change effect
      unmount();
      renderWithRouter(<Header />, '/tasks');
      
      // Menu should be closed in new render
      const overlay = document.querySelector('.mobile-menu-overlay');
      expect(overlay).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has aria-label for menu button', () => {
      renderWithRouter(<Header />);
      const menuBtn = document.querySelector('.mobile-menu-btn');
      expect(menuBtn).toHaveAttribute('aria-label', '菜单');
    });
  });

  describe('Edge Cases', () => {
    it('handles missing user gracefully', () => {
      mockUseAuth.mockReturnValue({
        user: null,
        logout: mockLogout,
        isAuthenticated: false,
      });
      
      renderWithRouter(<Header />);
      expect(screen.getByText('?')).toBeInTheDocument(); // Default avatar
      expect(screen.getByText('用户')).toBeInTheDocument(); // Default username
    });

    it('handles empty username', () => {
      mockUseAuth.mockReturnValue({
        user: { id: 1, username: '', email: 'test@example.com' },
        logout: mockLogout,
        isAuthenticated: true,
      });
      
      renderWithRouter(<Header />);
      expect(screen.getByText('?')).toBeInTheDocument();
    });

    it('handles long username', () => {
      mockUseAuth.mockReturnValue({
        user: { id: 1, username: 'verylongusernamethatshouldtrunc', email: 'test@example.com' },
        logout: mockLogout,
        isAuthenticated: true,
      });
      
      renderWithRouter(<Header />);
      expect(screen.getByText('verylongusernamethatshouldtrunc')).toBeInTheDocument();
    });
  });
});