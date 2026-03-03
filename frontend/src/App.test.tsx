import React from 'react';
import { render, screen } from '@testing-library/react';

// Mock useAuth hook
jest.mock('./hooks/useAuth', () => ({
  useAuth: () => ({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    login: jest.fn(),
    logout: jest.fn(),
    checkAuth: jest.fn(),
  }),
}));

// Mock axios
jest.mock('axios', () => ({
  create: jest.fn(() => ({
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  })),
}));

import App from './App';

test('renders login page when not authenticated', () => {
  render(<App />);
  expect(screen.getByText(/登录页面/i)).toBeInTheDocument();
});