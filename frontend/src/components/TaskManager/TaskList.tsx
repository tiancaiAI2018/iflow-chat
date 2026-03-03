import React from 'react';
import type { Task } from '../../types';
import './TaskManager.css';

interface TaskListProps {
  tasks: Task[];
  isLoading: boolean;
  onToggle: (taskId: string) => Promise<void>;
  onDelete: (taskId: string) => Promise<void>;
}

const TaskList: React.FC<TaskListProps> = ({ tasks, isLoading, onToggle, onDelete }) => {
  const [togglingId, setTogglingId] = React.useState<string | null>(null);
  const [deletingId, setDeletingId] = React.useState<string | null>(null);

  const handleToggle = async (taskId: string) => {
    setTogglingId(taskId);
    try {
      await onToggle(taskId);
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (taskId: string) => {
    if (!window.confirm('确定要删除这个任务吗？')) {
      return;
    }
    setDeletingId(taskId);
    try {
      await onDelete(taskId);
    } finally {
      setDeletingId(null);
    }
  };

  // 格式化时间显示
  const formatTime = (dateStr: string | null) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // 解析 Cron 表达式为可读文本
  const parseCron = (cron: string): string => {
    const parts = cron.split(' ');
    if (parts.length !== 5) return cron;

    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

    // 每分钟
    if (cron === '* * * * *') return '每分钟';

    // 每小时
    if (minute !== '*' && hour === '*') return `每小时 ${minute} 分`;

    // 每天
    if (dayOfMonth === '*' && month === '*' && dayOfWeek === '*') {
      return `每天 ${hour}:${minute.padStart(2, '0')}`;
    }

    // 每周
    if (dayOfWeek !== '*') {
      const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
      return `每${days[parseInt(dayOfWeek)]} ${hour}:${minute.padStart(2, '0')}`;
    }

    // 每月
    if (dayOfMonth !== '*') {
      return `每月 ${dayOfMonth} 日 ${hour}:${minute.padStart(2, '0')}`;
    }

    return cron;
  };

  if (isLoading) {
    return (
      <div className="task-list-loading">
        <div className="loading-spinner"></div>
        <span>加载任务列表...</span>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="task-list-empty">
        <div className="empty-icon">📋</div>
        <div className="empty-text">暂无定时任务</div>
        <div className="empty-hint">使用自然语言创建任务，例如："每天早上9点提醒我查看股票"</div>
      </div>
    );
  }

  return (
    <div className="task-list">
      {tasks.map((task) => (
        <div key={task.id} className={`task-item ${task.enabled ? 'enabled' : 'disabled'}`}>
          <div className="task-header">
            <div className="task-content">{task.content}</div>
            <div className="task-actions">
              <button
                className={`toggle-btn ${task.enabled ? 'on' : 'off'}`}
                onClick={() => handleToggle(task.id)}
                disabled={togglingId === task.id}
                title={task.enabled ? '点击禁用' : '点击启用'}
              >
                {togglingId === task.id ? (
                  <span className="btn-loading"></span>
                ) : task.enabled ? (
                  '✓ 启用'
                ) : (
                  '○ 禁用'
                )}
              </button>
              <button
                className="delete-btn"
                onClick={() => handleDelete(task.id)}
                disabled={deletingId === task.id}
                title="删除任务"
              >
                {deletingId === task.id ? (
                  <span className="btn-loading"></span>
                ) : (
                  '🗑️'
                )}
              </button>
            </div>
          </div>

          <div className="task-meta">
            <div className="task-schedule">
              <span className="schedule-icon">⏰</span>
              <span className="schedule-text">{parseCron(task.cron)}</span>
              <span className="schedule-original">({task.natural_language})</span>
            </div>
            
            <div className="task-times">
              {task.last_run && (
                <span className="task-time">
                  上次执行: {formatTime(task.last_run)}
                </span>
              )}
              {task.next_run && task.enabled && (
                <span className="task-time next">
                  下次执行: {formatTime(task.next_run)}
                </span>
              )}
            </div>
          </div>

          <div className="task-cron">
            <code>{task.cron}</code>
          </div>
        </div>
      ))}
    </div>
  );
};

export default TaskList;
