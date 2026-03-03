import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Register from './Register';

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
    register: jest.fn().mockResolvedValue({
      success: true,
      token: 'test-token',
      user: { id: 1, username: 'testuser', email: 'test@example.com' },
    }),
  },
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('Register Component', () => {
  it('renders register form', () => {
    renderWithRouter(<Register />);
    expect(screen.getByRole('heading', { name: '注册' })).toBeInTheDocument();
    expect(screen.getByLabelText(/用户名/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/邮箱/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^密码$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/确认密码/i)).toBeInTheDocument();
  });

  it('renders login link', () => {
    renderWithRouter(<Register />);
    expect(screen.getByText('立即登录')).toBeInTheDocument();
  });

  it('shows error for short username', async () => {
    renderWithRouter(<Register />);
    const usernameInput = screen.getByLabelText(/用户名/i);
    const submitBtn = screen.getByRole('button', { name: /^注册$/ });

    fireEvent.change(usernameInput, { target: { value: 'ab' } });
    fireEvent.click(submitBtn);

    await screen.findByText(/用户名至少3个字符/i);
  });

  it('shows error for invalid email', async () => {
    renderWithRouter(<Register />);
    const usernameInput = screen.getByLabelText(/用户名/i);
    const emailInput = screen.getByLabelText(/邮箱/i);
    const submitBtn = screen.getByRole('button', { name: /^注册$/ });

    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    fireEvent.click(submitBtn);

    await screen.findByText(/邮箱格式不正确/i);
  });

  it('shows error for short password', async () => {
    renderWithRouter(<Register />);
    const usernameInput = screen.getByLabelText(/用户名/i);
    const emailInput = screen.getByLabelText(/邮箱/i);
    const passwordInput = screen.getByLabelText(/^密码$/i);
    const submitBtn = screen.getByRole('button', { name: /^注册$/ });

    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: '123' } });
    fireEvent.click(submitBtn);

    await screen.findByText(/密码至少6个字符/i);
  });

  it('shows error for mismatched passwords', async () => {
    renderWithRouter(<Register />);
    const usernameInput = screen.getByLabelText(/用户名/i);
    const emailInput = screen.getByLabelText(/邮箱/i);
    const passwordInput = screen.getByLabelText(/^密码$/i);
    const confirmPasswordInput = screen.getByLabelText(/确认密码/i);
    const submitBtn = screen.getByRole('button', { name: /^注册$/ });

    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'password456' } });
    fireEvent.click(submitBtn);

    await screen.findByText(/两次密码输入不一致/i);
  });
});
