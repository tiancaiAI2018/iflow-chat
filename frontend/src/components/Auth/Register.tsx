import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { apiService } from '../../services/api';
import type { RegisterRequest } from '../../types';
import './Auth.css';

interface RegisterForm {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
}

const Register: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [formData, setFormData] = useState<RegisterForm>({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError(null);
  };

  const validateForm = (): boolean => {
    if (!formData.username.trim()) {
      setError('用户名不能为空');
      return false;
    }
    if (formData.username.length < 3) {
      setError('用户名至少3个字符');
      return false;
    }
    if (!formData.email.trim()) {
      setError('邮箱不能为空');
      return false;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setError('邮箱格式不正确');
      return false;
    }
    if (formData.password.length < 6) {
      setError('密码至少6个字符');
      return false;
    }
    if (formData.password !== formData.confirmPassword) {
      setError('两次密码输入不一致');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setLoading(true);
    setError(null);

    try {
      const requestData: RegisterRequest = {
        username: formData.username,
        email: formData.email,
        password: formData.password,
      };
      const response = await apiService.register(requestData);
      if (response.success && response.token && response.user) {
        login(response.token, response.user);
        navigate('/chat');
      } else {
        setError(response.message || '注册失败，请重试');
      }
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(axiosError.response?.data?.detail || '注册失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">注册</h1>
        <p className="auth-subtitle">创建您的 iFlow Chat 账号</p>

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
            <label htmlFor="email">邮箱</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="请输入邮箱"
              required
              autoComplete="email"
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
              placeholder="请输入密码（至少6位）"
              required
              autoComplete="new-password"
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">确认密码</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="请再次输入密码"
              required
              autoComplete="new-password"
            />
          </div>

          <button type="submit" className="auth-btn primary" disabled={loading}>
            {loading ? '注册中...' : '注册'}
          </button>
        </form>

        <div className="auth-divider">
          <span>或</span>
        </div>

        <button
          onClick={() => navigate('/login-email')}
          className="auth-btn secondary"
        >
          邮箱验证码注册
        </button>

        <div className="auth-footer">
          <span>已有账号？</span>
          <Link to="/login">立即登录</Link>
        </div>
      </div>
    </div>
  );
};

export default Register;
