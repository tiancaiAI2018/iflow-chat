import React, { useMemo } from 'react';
import { marked } from 'marked';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import type { ToolCall } from '../../types';
import { ToolCallList } from '../ToolCall/ToolCall';
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
          <ToolCallList toolCalls={toolCalls} />
        )}
      </div>
    </div>
  );
};

export default Message;
