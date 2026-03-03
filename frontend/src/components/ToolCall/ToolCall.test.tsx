import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ToolCall, { ToolCallList } from './ToolCall';
import type { ToolCall as ToolCallType } from '../../types';

// 模拟 types
jest.mock('../../types', () => ({}));

describe('ToolCall Component', () => {
  const mockToolCall: ToolCallType = {
    tool_name: 'read_file',
    arguments: { path: '/test/file.txt' },
    status: 'completed',
    result: 'File content here',
  };

  it('renders tool call card with basic info', () => {
    render(<ToolCall toolCall={mockToolCall} />);
    
    expect(screen.getByText('read_file')).toBeInTheDocument();
    expect(screen.getByText('✅')).toBeInTheDocument();
  });

  it('shows tool icon based on tool name', () => {
    const { rerender } = render(<ToolCall toolCall={mockToolCall} />);
    expect(screen.getByText('📄')).toBeInTheDocument(); // read_file icon

    rerender(<ToolCall toolCall={{ ...mockToolCall, tool_name: 'write_file' }} />);
    expect(screen.getByText('✏️')).toBeInTheDocument(); // write_file icon

    rerender(<ToolCall toolCall={{ ...mockToolCall, tool_name: 'run_shell_command' }} />);
    expect(screen.getByText('💻')).toBeInTheDocument(); // shell command icon

    rerender(<ToolCall toolCall={{ ...mockToolCall, tool_name: 'unknown_tool' }} />);
    expect(screen.getByText('🔧')).toBeInTheDocument(); // default icon
  });

  it('shows correct status icons', () => {
    const { rerender } = render(<ToolCall toolCall={{ ...mockToolCall, status: 'pending' }} />);
    expect(screen.getByText('⏳')).toBeInTheDocument();

    rerender(<ToolCall toolCall={{ ...mockToolCall, status: 'in_progress' }} />);
    expect(screen.getByText('🔄')).toBeInTheDocument();

    rerender(<ToolCall toolCall={{ ...mockToolCall, status: 'completed' }} />);
    expect(screen.getByText('✅')).toBeInTheDocument();

    rerender(<ToolCall toolCall={{ ...mockToolCall, status: 'failed' }} />);
    expect(screen.getByText('❌')).toBeInTheDocument();
  });

  it('expands and collapses on header click', () => {
    render(<ToolCall toolCall={mockToolCall} />);
    
    // 初始状态：折叠，不显示参数和结果
    expect(screen.queryByText('参数')).not.toBeInTheDocument();
    
    // 点击展开
    fireEvent.click(screen.getByText('read_file'));
    expect(screen.getByText('参数')).toBeInTheDocument();
    expect(screen.getByText('结果')).toBeInTheDocument();
    
    // 再次点击折叠
    fireEvent.click(screen.getByText('read_file'));
    expect(screen.queryByText('参数')).not.toBeInTheDocument();
  });

  it('shows arguments when expanded', () => {
    render(<ToolCall toolCall={mockToolCall} defaultExpanded={true} />);
    
    expect(screen.getByText('参数')).toBeInTheDocument();
    expect(screen.getByText(/"path"/)).toBeInTheDocument();
    expect(screen.getByText(/"\/test\/file.txt"/)).toBeInTheDocument();
  });

  it('shows result when expanded', () => {
    render(<ToolCall toolCall={mockToolCall} defaultExpanded={true} />);
    
    expect(screen.getByText('结果')).toBeInTheDocument();
    expect(screen.getByText('File content here')).toBeInTheDocument();
  });

  it('handles empty arguments', () => {
    const toolCallNoArgs: ToolCallType = {
      tool_name: 'test_tool',
      arguments: {},
      status: 'completed',
    };
    
    render(<ToolCall toolCall={toolCallNoArgs} defaultExpanded={true} />);
    
    // 参数区域不应显示
    expect(screen.queryByText('参数')).not.toBeInTheDocument();
  });

  it('handles undefined result', () => {
    const toolCallNoResult: ToolCallType = {
      tool_name: 'test_tool',
      arguments: { test: 'value' },
      status: 'pending',
    };
    
    render(<ToolCall toolCall={toolCallNoResult} defaultExpanded={true} />);
    
    // 结果区域不应显示
    expect(screen.queryByText('结果')).not.toBeInTheDocument();
  });

  it('displays status label', () => {
    const { rerender } = render(<ToolCall toolCall={mockToolCall} defaultExpanded={true} />);
    expect(screen.getByText('成功')).toBeInTheDocument();

    rerender(<ToolCall toolCall={{ ...mockToolCall, status: 'pending' }} defaultExpanded={true} />);
    expect(screen.getByText('等待中')).toBeInTheDocument();

    rerender(<ToolCall toolCall={{ ...mockToolCall, status: 'in_progress' }} defaultExpanded={true} />);
    expect(screen.getByText('执行中')).toBeInTheDocument();

    rerender(<ToolCall toolCall={{ ...mockToolCall, status: 'failed' }} defaultExpanded={true} />);
    expect(screen.getByText('失败')).toBeInTheDocument();
  });

  it('shows error styling for failed tool calls', () => {
    const failedToolCall: ToolCallType = {
      tool_name: 'test_tool',
      arguments: {},
      status: 'failed',
      result: 'Error: Something went wrong',
    };
    
    render(<ToolCall toolCall={failedToolCall} defaultExpanded={true} />);
    
    const codeElement = screen.getByText(/Error: Something went wrong/).closest('pre');
    expect(codeElement).toHaveClass('error');
  });

  it('truncates long results', () => {
    const longResult = 'A'.repeat(600);
    const toolCallLongResult: ToolCallType = {
      tool_name: 'test_tool',
      arguments: {},
      status: 'completed',
      result: longResult,
    };
    
    render(<ToolCall toolCall={toolCallLongResult} defaultExpanded={true} />);
    
    expect(screen.getByText(/\[内容已截断/)).toBeInTheDocument();
  });

  it('applies status-based CSS classes', () => {
    const { container, rerender } = render(<ToolCall toolCall={{ ...mockToolCall, status: 'pending' }} />);
    expect(container.querySelector('.tool-call-card')).toHaveClass('pending');

    rerender(<ToolCall toolCall={{ ...mockToolCall, status: 'in_progress' }} />);
    expect(container.querySelector('.tool-call-card')).toHaveClass('in_progress');

    rerender(<ToolCall toolCall={{ ...mockToolCall, status: 'completed' }} />);
    expect(container.querySelector('.tool-call-card')).toHaveClass('completed');

    rerender(<ToolCall toolCall={{ ...mockToolCall, status: 'failed' }} />);
    expect(container.querySelector('.tool-call-card')).toHaveClass('failed');
  });
});

describe('ToolCallList Component', () => {
  const mockToolCalls: ToolCallType[] = [
    {
      tool_name: 'read_file',
      arguments: { path: '/file1.txt' },
      status: 'completed',
      result: 'content 1',
    },
    {
      tool_name: 'write_file',
      arguments: { path: '/file2.txt', content: 'test' },
      status: 'in_progress',
    },
  ];

  it('renders multiple tool calls', () => {
    render(<ToolCallList toolCalls={mockToolCalls} />);
    
    expect(screen.getByText('read_file')).toBeInTheDocument();
    expect(screen.getByText('write_file')).toBeInTheDocument();
  });

  it('returns null for empty array', () => {
    const { container } = render(<ToolCallList toolCalls={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null for undefined', () => {
    const { container } = render(<ToolCallList toolCalls={undefined as any} />);
    expect(container.firstChild).toBeNull();
  });

  it('passes defaultExpanded prop to children', () => {
    render(<ToolCallList toolCalls={mockToolCalls} defaultExpanded={true} />);
    
    // 所有工具调用应该展开，显示参数
    expect(screen.getAllByText('参数')).toHaveLength(2);
  });

  it('auto-expands failed tool calls', () => {
    const toolCallsWithFailed: ToolCallType[] = [
      {
        tool_name: 'read_file',
        arguments: { path: '/file.txt' },
        status: 'failed',
        result: 'Error',
      },
    ];
    
    render(<ToolCallList toolCalls={toolCallsWithFailed} />);
    
    // 失败的工具调用应该自动展开
    expect(screen.getByText('参数')).toBeInTheDocument();
  });
});
