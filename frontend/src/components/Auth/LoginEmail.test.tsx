import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import LoginEmail from './LoginEmail';

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
const mockSendCode = jest.fn().mockResolvedValue({ success: true });
const mockVerifyCode = jest.fn().mockResolvedValue({
  success: true,
  token: 'test-token',
  user: { id: 1, username: 'testuser', email: 'test@example.com' },
});

jest.mock('../../services/api', () => ({
  apiService: {
    sendCode: () => mockSendCode(),
    verifyCode: () => mockVerifyCode(),
  },
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe('LoginEmail Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders email input step by default', () => {
    renderWithRouter(<LoginEmail />);
    expect(screen.getByText('邮箱验证码登录')).toBeInTheDocument();
    expect(screen.getByLabelText(/邮箱地址/i)).toBeInTheDocument();
  });

  it('shows error for invalid email', async () => {
    renderWithRouter(<LoginEmail />);
    const emailInput = screen.getByLabelText(/邮箱地址/i);
    const submitBtn = screen.getByRole('button', { name: /发送验证码/i });

    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    fireEvent.click(submitBtn);

    await screen.findByText(/请输入正确的邮箱地址/i);
  });

  it('renders username login link', () => {
    renderWithRouter(<LoginEmail />);
    expect(screen.getByText('用户名密码登录')).toBeInTheDocument();
  });

  it('renders register link', () => {
    renderWithRouter(<LoginEmail />);
    expect(screen.getByText('立即注册')).toBeInTheDocument();
  });

  it('disables send code button when email is empty', () => {
    renderWithRouter(<LoginEmail />);
    const submitBtn = screen.getByRole('button', { name: /发送验证码/i });
    expect(submitBtn).toBeDisabled();
  });

  it('enables send code button when email is entered', () => {
    renderWithRouter(<LoginEmail />);
    const emailInput = screen.getByLabelText(/邮箱地址/i);
    const submitBtn = screen.getByRole('button', { name: /发送验证码/i });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    expect(submitBtn).not.toBeDisabled();
  });
});
