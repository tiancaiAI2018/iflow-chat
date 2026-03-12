import React, { useState, useEffect } from 'react';
import { apiService } from '../../services/api';
import './Settings.css';

interface PushKeySettingsProps {
  isOpen: boolean;
  onClose: () => void;
  currentPushKey?: string | null;
  onUpdated: (pushKey: string | null) => void;
}

const PushKeySettings: React.FC<PushKeySettingsProps> = ({
  isOpen,
  onClose,
  currentPushKey,
  onUpdated,
}) => {
  const [pushKey, setPushKey] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (isOpen) {
      setPushKey(currentPushKey || '');
      setMessage(null);
    }
  }, [isOpen, currentPushKey]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage(null);

    try {
      const response = await apiService.updatePushKey(pushKey.trim() || null);
      if (response.success) {
        setMessage({ type: 'success', text: response.message });
        onUpdated(response.push_key);
        setTimeout(() => {
          onClose();
        }, 1500);
      } else {
        setMessage({ type: 'error', text: response.message || '更新失败' });
      }
    } catch (error: any) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.detail || '更新失败，请重试' 
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = async () => {
    if (!window.confirm('确定要清除推送密钥吗？清除后将无法收到定时任务的手机推送。')) {
      return;
    }

    setIsLoading(true);
    setMessage(null);

    try {
      const response = await apiService.updatePushKey(null);
      if (response.success) {
        setMessage({ type: 'success', text: '推送密钥已清除' });
        setPushKey('');
        onUpdated(null);
      } else {
        setMessage({ type: 'error', text: response.message || '清除失败' });
      }
    } catch (error: any) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.detail || '清除失败，请重试' 
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="settings-modal-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-modal-header">
          <h3>推送设置</h3>
          <button className="settings-close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="settings-form">
          <div className="settings-info">
            <p>
              <strong>PushMe</strong> 是一个轻量的手机消息推送服务。
              配置推送密钥后，定时任务执行结果会推送到您的手机。
            </p>
            <p className="settings-link">
              <a href="https://push.i-i.me/" target="_blank" rel="noopener noreferrer">
                获取 PushMe 推送密钥 →
              </a>
            </p>
          </div>

          <div className="settings-field">
            <label htmlFor="push_key">推送密钥 (push_key)</label>
            <input
              type="text"
              id="push_key"
              value={pushKey}
              onChange={(e) => setPushKey(e.target.value)}
              placeholder="在 PushMe APP 上获取"
              disabled={isLoading}
            />
          </div>

          {message && (
            <div className={`settings-message ${message.type}`}>
              {message.text}
            </div>
          )}

          <div className="settings-actions">
            <button
              type="button"
              className="settings-btn secondary"
              onClick={handleClear}
              disabled={isLoading || !currentPushKey}
            >
              清除
            </button>
            <button
              type="submit"
              className="settings-btn primary"
              disabled={isLoading}
            >
              {isLoading ? '保存中...' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default PushKeySettings;
