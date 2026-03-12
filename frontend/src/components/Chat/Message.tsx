import React, { useMemo, useState } from 'react';
import { marked } from 'marked';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import type { ToolCall, PlanEntry } from '../../types';
import { ToolCallList } from '../ToolCall/ToolCall';
import ToolCallItem from '../ToolCall/ToolCall';
import './Chat.css';

// 消息中的附件信息
interface MessageAttachment {
  name: string;
  type: 'image' | 'file';
  size: number;
  preview?: string;
}

interface MessageProps {
  id: string;
  role: 'user' | 'assistant' | 'tool_call' | 'plan';
  content: string;
  isStreaming?: boolean;
  isWaiting?: boolean;  // 等待后端响应中
  toolCalls?: ToolCall[];
  toolCall?: ToolCall;  // 单个工具调用（用于独立的工具调用消息）
  planEntries?: PlanEntry[];  // 任务计划条目
  created_at: string;
  attachments?: MessageAttachment[];
}

// 配置 marked 使用 highlight.js
const renderer = new marked.Renderer();
marked.setOptions({
  renderer,
  breaks: true,
  gfm: true,
});

// 生成唯一ID
let copyIdCounter = 0;
const generateCopyId = () => `copy-btn-${++copyIdCounter}`;

// 复制到剪贴板（支持非安全上下文）
const copyToClipboard = async (text: string): Promise<boolean> => {
  try {
    // 优先使用 Clipboard API（安全上下文）
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    // Fallback: 使用 execCommand（兼容非 HTTPS 环境）
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const success = document.execCommand('copy');
    document.body.removeChild(textarea);
    return success;
  } catch (err) {
    console.error('Failed to copy:', err);
    return false;
  }
};

// 渲染 Markdown 内容并添加复制按钮
const renderMarkdown = (content: string): string => {
  try {
    const html = marked.parse(content) as string;
    const container = document.createElement('div');
    container.innerHTML = html;
    
    // 对代码块应用 highlight.js 并添加复制按钮
    container.querySelectorAll('pre').forEach((pre) => {
      const code = pre.querySelector('code');
      if (code) {
        hljs.highlightElement(code as HTMLElement);
      }
      
      // 为每个代码块添加包装器和复制按钮
      const wrapper = document.createElement('div');
      wrapper.className = 'code-block-wrapper';
      pre.parentNode?.insertBefore(wrapper, pre);
      wrapper.appendChild(pre);
      
      // 创建复制按钮
      const copyBtn = document.createElement('button');
      const btnId = generateCopyId();
      copyBtn.className = 'code-copy-btn';
      copyBtn.id = btnId;
      copyBtn.innerHTML = '📋';
      copyBtn.title = '复制代码';
      copyBtn.setAttribute('data-code', pre.textContent || '');
      wrapper.appendChild(copyBtn);
    });
    
    return container.innerHTML;
  } catch {
    return content;
  }
};

// 复制按钮组件（用于消息整体复制）
const CopyButton: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const success = await copyToClipboard(text);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button 
      className="copy-button message-copy-btn" 
      onClick={handleCopy}
      title={copied ? '已复制' : '复制'}
    >
      {copied ? '✓' : '📋'}
    </button>
  );
};

// 消息组件
const Message: React.FC<MessageProps> = ({
  role,
  content,
  isStreaming,
  isWaiting,
  toolCalls,
  toolCall,
  planEntries,
  attachments,
}) => {
  const htmlContent = useMemo(() => renderMarkdown(content), [content]);
  const [isHovered, setIsHovered] = useState(false);

  // 处理代码块复制按钮点击
  const handleTextClick = async (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.classList.contains('code-copy-btn')) {
      const code = target.getAttribute('data-code') || '';
      const success = await copyToClipboard(code);
      if (success) {
        target.innerHTML = '✓';
        target.title = '已复制';
        setTimeout(() => {
          target.innerHTML = '📋';
          target.title = '复制代码';
        }, 2000);
      }
    }
  };

  // 格式化文件大小
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // 独立的工具调用消息
  if (role === 'tool_call' && toolCall) {
    return (
      <div className="message message-tool_call">
        <div className="message-avatar">🔧</div>
        <div className="message-content">
          <ToolCallItem toolCall={toolCall} />
        </div>
      </div>
    );
  }

  // 任务计划消息
  if (role === 'plan' && planEntries && planEntries.length > 0) {
    return (
      <div className="message message-plan">
        <div className="message-avatar">📋</div>
        <div className="message-content">
          <div className="plan-container">
            <div className="plan-header">任务计划</div>
            <div className="plan-entries">
              {planEntries.map((entry, index) => (
                <div key={index} className={`plan-entry plan-entry-${entry.status} plan-priority-${entry.priority}`}>
                  <span className="plan-status-icon">
                    {entry.status === 'completed' ? '✅' : entry.status === 'in_progress' ? '🔄' : '⏳'}
                  </span>
                  <span className="plan-content">{entry.content}</span>
                  <span className={`plan-priority plan-priority-${entry.priority}`}>
                    {entry.priority === 'high' ? '高' : entry.priority === 'medium' ? '中' : '低'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div 
      className={`message message-${role}`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="message-avatar">
        {role === 'user' ? '👤' : '🤖'}
      </div>
      <div className="message-content">
        {/* 等待状态显示加载动画 */}
        {isWaiting && !content && (
          <div className="message-waiting">
            <div className="waiting-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        {/* 用户附件显示 */}
        {role === 'user' && attachments && attachments.length > 0 && (
          <div className="message-attachments">
            {attachments.map((attachment, index) => (
              <div key={index} className="message-attachment-item">
                {attachment.type === 'image' && attachment.preview ? (
                  <img 
                    src={attachment.preview} 
                    alt={attachment.name}
                    className="message-attachment-image"
                  />
                ) : (
                  <div className="message-attachment-file">
                    <span className="file-icon">📄</span>
                    <div className="file-info">
                      <span className="file-name">{attachment.name}</span>
                      <span className="file-size">{formatFileSize(attachment.size)}</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {content && (
          <div className="message-text-wrapper">
            <div
              className="message-text"
              dangerouslySetInnerHTML={{ __html: htmlContent }}
              onClick={handleTextClick}
            />
            {/* 消息整体复制按钮 - 仅在非流式输出且悬停时显示 */}
            {!isStreaming && isHovered && content && (
              <CopyButton text={content} />
            )}
          </div>
        )}
        {isStreaming && <span className="message-cursor">▊</span>}
        {toolCalls && toolCalls.length > 0 && (
          <ToolCallList toolCalls={toolCalls} />
        )}
      </div>
    </div>
  );
};

export default Message;
