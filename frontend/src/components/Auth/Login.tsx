import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { apiService } from '../../services/api';
import type { LoginRequest } from '../../types';
import './Auth.css';

interface LoginForm {
  username: string;
  password: string;
}

const Login: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [formData, setFormData] = useState<LoginForm>({
    username: '',
    password: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await apiService.login(formData as LoginRequest);
      if (response.success && response.token && response.user) {
        login(response.token, response.user);
        navigate('/chat');
      } else {
        setError(response.message || '登录失败，请重试');
      }
    } catch (err) {
      setError('登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  const handleEmailLogin = () => {
    navigate('/login-email');
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">登录</h1>
        <p className="auth-subtitle">欢迎回到 iFlow Chat</p>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error">{error}</div>}

          <div className="form-group">
            <label htmlFor="username">用户名</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="请输入用户名"
              required
              autoComplete="username"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">密码</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="请输入密码"
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="auth-btn primary" disabled={loading}>
            {loading ? '登录中...' : '登录'}
          </button>
        </form>

        <div className="auth-divider">
          <span>或</span>
        </div>

        <button onClick={handleEmailLogin} className="auth-btn secondary">
          邮箱验证码登录
        </button>

        <div className="auth-footer">
          <span>还没有账号？</span>
          <Link to="/register">立即注册</Link>
        </div>
      </div>
    </div>
  );
};

export default Login;
