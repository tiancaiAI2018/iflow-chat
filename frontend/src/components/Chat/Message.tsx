import React, { useMemo } from 'react';
import { marked } from 'marked';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import type { ToolCall } from '../../types';
import { ToolCallList } from '../ToolCall/ToolCall';
import ToolCallItem from '../ToolCall/ToolCall';
import './Chat.css';

interface MessageProps {
  id: string;
  role: 'user' | 'assistant' | 'tool_call';
  content: string;
  isStreaming?: boolean;
  toolCalls?: ToolCall[];
  toolCall?: ToolCall;  // 单个工具调用（用于独立的工具调用消息）
  created_at: string;
}

// 配置 marked 使用 highlight.js
const renderer = new marked.Renderer();
marked.setOptions({
  renderer,
  breaks: true,
  gfm: true,
});

// 渲染 Markdown 内容
const renderMarkdown = (content: string): string => {
  try {
    const html = marked.parse(content) as string;
    // 对代码块应用 highlight.js
    const container = document.createElement('div');
    container.innerHTML = html;
    container.querySelectorAll('pre code').forEach((block) => {
      hljs.highlightElement(block as HTMLElement);
    });
    return container.innerHTML;
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
  toolCall,
}) => {
  const htmlContent = useMemo(() => renderMarkdown(content), [content]);

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
