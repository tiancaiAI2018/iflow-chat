import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Login from './Login';

// Mock useAuth hook
jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    login: jest.fn(),
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
  }),
}));

// Mock apiService
jest.mock('../../services/api', () => ({
  apiService: {
    login: jest.fn().mockResolvedValue({
      success: true,
      token: 'test-token',
      user: { id: 1, username: 'testuser', email: 'test@example.com' },
    }),
  },
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('Login Component', () => {
  it('renders login form', () => {
    renderWithRouter(<Login />);
    expect(screen.getByRole('heading', { name: '登录' })).toBeInTheDocument();
    expect(screen.getByLabelText(/用户名/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/密码/i)).toBeInTheDocument();
  });

  it('renders email login button', () => {
    renderWithRouter(<Login />);
    expect(screen.getByText('邮箱验证码登录')).toBeInTheDocument();
  });

  it('renders register link', () => {
    renderWithRouter(<Login />);
    expect(screen.getByText('立即注册')).toBeInTheDocument();
  });

  it('shows error when submitting empty form', async () => {
    renderWithRouter(<Login />);
    const submitBtn = screen.getByRole('button', { name: /^登录$/ });
    fireEvent.click(submitBtn);
    // HTML5 form validation should prevent submission
  });

  it('updates form data on input change', () => {
    renderWithRouter(<Login />);
    const usernameInput = screen.getByLabelText(/用户名/i) as HTMLInputElement;
    const passwordInput = screen.getByLabelText(/密码/i) as HTMLInputElement;

    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'testpass' } });

    expect(usernameInput.value).toBe('testuser');
    expect(passwordInput.value).toBe('testpass');
  });
});