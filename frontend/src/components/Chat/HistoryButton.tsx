import React from 'react';
import './HistoryButton.css';

interface HistoryButtonProps {
  className?: string;
  onClick?: () => void;
}

/**
 * 历史会话按钮组件
 * 点击打开会话抽屉
 */
const HistoryButton: React.FC<HistoryButtonProps> = ({ className = '', onClick }) => {
  const handleClick = () => {
    onClick?.();
  };

  return (
    <button
      type="button"
      className={`history-button ${className}`}
      onClick={handleClick}
      title="历史会话"
      aria-label="历史会话"
    >
      <svg
        className="history-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="10" />
        <polyline points="12,6 12,12 16,14" />
      </svg>
      <span className="history-text">历史</span>
    </button>
  );
};

export default HistoryButton;
