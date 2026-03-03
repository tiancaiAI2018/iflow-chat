import React, { useMemo } from 'react';
import { marked } from 'marked';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import type { ToolCall } from '../../types';
import './Chat.css';

interface MessageProps {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
  toolCalls?: ToolCall[];
  created_at: string;
}

// 配置 marked 使用 highlight.js
marked.setOptions({
  highlight: function (code: string, lang: string) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value;
      } catch {
        return code;
      }
    }
    return hljs.highlightAuto(code).value;
  },
  breaks: true,
  gfm: true,
});

// 渲染 Markdown 内容
const renderMarkdown = (content: string): string => {
  try {
    return marked.parse(content) as string;
  } catch {
    return content;
  }
};

// 工具调用卡片组件
const ToolCallCard: React.FC<{ toolCall: ToolCall }> = ({ toolCall }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const statusIcon = {
    pending: '⏳',
    in_progress: '🔄',
    completed: '✅',
    failed: '❌',
  }[toolCall.status] || '❓';

  const statusClass = `tool-call-status status-${toolCall.status}`;

  return (
    <div className="tool-call-card">
      <div className="tool-call-header" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="tool-call-icon">🔧</span>
        <span className="tool-call-name">{toolCall.tool_name}</span>
        <span className={statusClass}>{statusIcon}</span>
        <span className="tool-call-expand">{isExpanded ? '▼' : '▶'}</span>
      </div>
      {isExpanded && (
        <div className="tool-call-details">
          <div className="tool-call-section">
            <strong>参数:</strong>
            <pre className="tool-call-code">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>
          {toolCall.result !== undefined && (
            <div className="tool-call-section">
              <strong>结果:</strong>
              <pre className="tool-call-code">
                {typeof toolCall.result === 'string'
                  ? toolCall.result
                  : JSON.stringify(toolCall.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// 消息组件
const Message: React.FC<MessageProps> = ({
  role,
  content,
  isStreaming,
  toolCalls,
}) => {
  const htmlContent = useMemo(() => renderMarkdown(content), [content]);

  return (
    <div className={`message message-${role}`}>
      <div className="message-avatar">
        {role === 'user' ? '👤' : '🤖'}
      </div>
      <div className="message-content">
        {content && (
          <div
            className="message-text"
            dangerouslySetInnerHTML={{ __html: htmlContent }}
          />
        )}
        {isStreaming && <span className="message-cursor">▊</span>}
        {toolCalls && toolCalls.length > 0 && (
          <div className="message-tool-calls">
            {toolCalls.map((tc, index) => (
              <ToolCallCard key={`${tc.tool_name}-${index}`} toolCall={tc} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Message;
