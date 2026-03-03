import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { apiService } from '../../services/api';
import './Auth.css';

type Step = 'email' | 'code';

const LoginEmail: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [loading, setLoading] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);
  
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // 倒计时逻辑
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  // 验证邮箱格式
  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  // 发送验证码
  const handleSendCode = async () => {
    if (!validateEmail(email)) {
      setError('请输入正确的邮箱地址');
      return;
    }

    setSendingCode(true);
    setError(null);

    try {
      const response = await apiService.sendCode({ email });
      if (response.success) {
        setSuccess('验证码已发送到您的邮箱');
        setCountdown(60); // 60秒倒计时
        setStep('code');
      } else {
        setError(response.message || '发送验证码失败');
      }
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(axiosError.response?.data?.detail || '发送验证码失败，请稍后重试');
    } finally {
      setSendingCode(false);
    }
  };

  // 处理验证码输入
  const handleCodeChange = useCallback((index: number, value: string) => {
    // 只允许数字
    const digit = value.replace(/\D/g, '').slice(-1);
    
    setCode(prev => {
      const newCode = [...prev];
      newCode[index] = digit;
      return newCode;
    });

    // 自动跳转到下一个输入框
    if (digit && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }

    // 当输入完6位后自动提交
    if (digit && index === 5) {
      const fullCode = [...code.slice(0, index), digit, ...code.slice(index + 1)].join('');
      if (fullCode.length === 6) {
        handleVerifyCode([...code.slice(0, index), digit, ...code.slice(index + 1)].join(''));
      }
    }
  }, [code]);

  // 处理粘贴事件
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    
    if (pastedData) {
      const newCode = pastedData.split('').concat(['', '', '', '', '', '']).slice(0, 6);
      setCode(newCode);
      
      // 如果粘贴了6位，自动提交
      if (pastedData.length === 6) {
        handleVerifyCode(pastedData);
      } else {
        // 聚焦到下一个空输入框
        const nextIndex = pastedData.length;
        inputRefs.current[nextIndex]?.focus();
      }
    }
  }, []);

  // 处理键盘事件
  const handleKeyDown = useCallback((index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      // 删除时如果没有内容，跳转到前一个输入框
      inputRefs.current[index - 1]?.focus();
    }
  }, [code]);

  // 验证码登录
  const handleVerifyCode = async (verifyCode?: string) => {
    const codeToUse = verifyCode || code.join('');
    
    if (codeToUse.length !== 6) {
      setError('请输入6位验证码');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiService.verifyCode({ email, code: codeToUse });
      if (response.success && response.token && response.user) {
        login(response.token, response.user);
        navigate('/chat');
      } else {
        setError(response.message || '验证失败');
      }
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      setError(axiosError.response?.data?.detail || '验证失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  // 重新发送验证码
  const handleResend = () => {
    if (countdown > 0) return;
    handleSendCode();
  };

  // 返回邮箱输入步骤
  const handleBack = () => {
    setStep('email');
    setCode(['', '', '', '', '', '']);
    setError(null);
    setSuccess(null);
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">邮箱验证码登录</h1>
        <p className="auth-subtitle">
          {step === 'email' ? '使用邮箱验证码快速登录/注册' : `验证码已发送至 ${email}`}
        </p>

        {step === 'email' ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendCode();
            }}
            className="auth-form"
          >
            {error && <div className="auth-error">{error}</div>}
            {success && <div className="auth-success">{success}</div>}

            <div className="form-group">
              <label htmlFor="email">邮箱地址</label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="请输入邮箱"
                required
                autoComplete="email"
              />
            </div>

            <button
              type="submit"
              className="auth-btn primary"
              disabled={sendingCode || !email}
            >
              {sendingCode ? '发送中...' : '发送验证码'}
            </button>

            <div className="auth-divider">
              <span>或</span>
            </div>

            <button
              type="button"
              onClick={() => navigate('/login')}
              className="auth-btn secondary"
            >
              用户名密码登录
            </button>

            <div className="auth-footer">
              <span>还没有账号？</span>
              <Link to="/register">立即注册</Link>
            </div>
          </form>
        ) : (
          <div className="email-code-container">
            {error && <div className="auth-error">{error}</div>}

            <div className="email-display">
              <span>{email}</span>
              <button type="button" onClick={handleBack}>
                更换邮箱
              </button>
            </div>

            <label className="form-group" style={{ textAlign: 'center' }}>
              请输入6位验证码
            </label>

            <div className="code-inputs">
              {code.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => {
                    inputRefs.current[index] = el;
                  }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleCodeChange(index, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(index, e)}
                  onPaste={handlePaste}
                  className={`code-input ${digit ? 'filled' : ''}`}
                  disabled={loading}
                />
              ))}
            </div>

            <button
              type="button"
              onClick={() => handleVerifyCode()}
              className="auth-btn primary"
              disabled={loading || code.some((c) => !c)}
            >
              {loading ? '验证中...' : '验证登录'}
            </button>

            <p className="timer-text">
              {countdown > 0 ? (
                <span className="counting">{countdown}秒后可重新发送</span>
              ) : (
                <button
                  type="button"
                  onClick={handleResend}
                  className="auth-btn email-btn"
                  style={{ width: '100%', marginTop: '8px' }}
                  disabled={sendingCode}
                >
                  {sendingCode ? '发送中...' : '重新发送验证码'}
                </button>
              )}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default LoginEmail;
