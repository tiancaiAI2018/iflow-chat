import React, { useState } from 'react';
import type { ToolCall as ToolCallType } from '../../types';
import './ToolCall.css';

interface ToolCallProps {
  toolCall: ToolCallType;
  defaultExpanded?: boolean;
}

// 状态图标映射
const STATUS_ICONS: Record<ToolCallType['status'], { icon: string; label: string }> = {
  pending: { icon: '⏳', label: '等待中' },
  in_progress: { icon: '🔄', label: '执行中' },
  completed: { icon: '✅', label: '成功' },
  failed: { icon: '❌', label: '失败' },
};

// 工具图标映射（常见工具）
const TOOL_ICONS: Record<string, string> = {
  read_file: '📄',
  write_file: '✏️',
  run_shell_command: '💻',
  glob: '🔍',
  search_file_content: '🔎',
  list_directory: '📁',
  web_search: '🌐',
  web_fetch: '🔗',
  browser_navigate: '🌐',
  browser_click: '👆',
  browser_snapshot: '📸',
  send_email: '📧',
  default: '🔧',
};

// 格式化参数显示
const formatArguments = (args: Record<string, unknown>): string => {
  return JSON.stringify(args, null, 2);
};

// 格式化结果显示
const formatResult = (result: unknown): string => {
  if (result === undefined || result === null) {
    return '无结果';
  }
  if (typeof result === 'string') {
    // 如果是长字符串，截断显示
    if (result.length > 500) {
      return result.substring(0, 500) + '...\n[内容已截断，点击展开查看完整内容]';
    }
    return result;
  }
  const jsonStr = JSON.stringify(result, null, 2);
  if (jsonStr.length > 500) {
    return jsonStr.substring(0, 500) + '...\n[内容已截断]';
  }
  return jsonStr;
};

// 工具调用卡片组件
const ToolCall: React.FC<ToolCallProps> = ({ toolCall, defaultExpanded = false }) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const statusInfo = STATUS_ICONS[toolCall.status] || { icon: '❓', label: '未知' };
  const toolIcon = TOOL_ICONS[toolCall.tool_name] || TOOL_ICONS.default;
  const statusClass = `tool-call-status status-${toolCall.status}`;

  // 获取工具名称（去掉前缀，更简洁）
  const displayName = toolCall.tool_name.replace(/^(browser_|mcp_)/, '');

  return (
    <div className={`tool-call-card ${toolCall.status}`}>
      <div className="tool-call-header" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="tool-call-icon">{toolIcon}</span>
        <span className="tool-call-name">{displayName}</span>
        <span className={statusClass} title={statusInfo.label}>
          {statusInfo.icon}
        </span>
        <span className={`tool-call-expand ${isExpanded ? 'expanded' : ''}`}>
          ▼
        </span>
      </div>

      {isExpanded && (
        <div className="tool-call-details">
          {/* 参数区域 */}
          {Object.keys(toolCall.arguments).length > 0 && (
            <div className="tool-call-section">
              <div className="tool-call-section-header">
                <span className="tool-call-section-icon">📥</span>
                <strong>参数</strong>
              </div>
              <pre className="tool-call-code">
                {formatArguments(toolCall.arguments)}
              </pre>
            </div>
          )}

          {/* 结果区域 */}
          {toolCall.result !== undefined && (
            <div className="tool-call-section">
              <div className="tool-call-section-header">
                <span className="tool-call-section-icon">📤</span>
                <strong>结果</strong>
              </div>
              <pre className={`tool-call-code ${toolCall.status === 'failed' ? 'error' : ''}`}>
                {formatResult(toolCall.result)}
              </pre>
            </div>
          )}

          {/* 状态信息 */}
          <div className="tool-call-status-info">
            <span className="status-label">状态:</span>
            <span className={`status-value status-${toolCall.status}`}>
              {statusInfo.label}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

// 工具调用列表组件
interface ToolCallListProps {
  toolCalls: ToolCallType[];
  defaultExpanded?: boolean;
}

export const ToolCallList: React.FC<ToolCallListProps> = ({ 
  toolCalls, 
  defaultExpanded = false 
}) => {
  if (!toolCalls || toolCalls.length === 0) {
    return null;
  }

  return (
    <div className="tool-call-list">
      {toolCalls.map((tc, index) => (
        <ToolCall 
          key={`${tc.tool_name}-${index}`} 
          toolCall={tc} 
          defaultExpanded={defaultExpanded || tc.status === 'failed'}
        />
      ))}
    </div>
  );
};

export default ToolCall;
