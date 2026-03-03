import React, { useEffect, useState, useCallback } from 'react';
import { apiService } from '../../services/api';
import type { Task } from '../../types';
import TaskList from './TaskList';
import TaskCreator from './TaskCreator';
import './TaskManager.css';

interface TaskManagerProps {
  onTaskCreated?: (task: Task) => void;
}

const TaskManager: React.FC<TaskManagerProps> = ({ onTaskCreated }) => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载任务列表
  const loadTasks = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiService.getTasks();
      setTasks(response.tasks || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载任务列表失败');
      console.error('Failed to load tasks:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // 创建任务
  const handleCreateTask = async (description: string) => {
    setIsCreating(true);
    try {
      const response = await apiService.createTask({ description });
      if (response.success && response.task) {
        setTasks((prev) => [response.task!, ...prev]);
        onTaskCreated?.(response.task);
      }
    } catch (err) {
      throw err;
    } finally {
      setIsCreating(false);
    }
  };

  // 切换任务状态
  const handleToggleTask = async (taskId: string) => {
    try {
      const response = await apiService.toggleTask(taskId);
      if (response.success) {
        setTasks((prev) =>
          prev.map((task) =>
            task.id === taskId ? { ...task, enabled: response.enabled } : task
          )
        );
      }
    } catch (err) {
      console.error('Failed to toggle task:', err);
      throw err;
    }
  };

  // 删除任务
  const handleDeleteTask = async (taskId: string) => {
    try {
      const response = await apiService.deleteTask(taskId);
      if (response.success) {
        setTasks((prev) => prev.filter((task) => task.id !== taskId));
      }
    } catch (err) {
      console.error('Failed to delete task:', err);
      throw err;
    }
  };

  // 统计任务数量
  const enabledCount = tasks.filter((t) => t.enabled).length;
  const totalCount = tasks.length;

  return (
    <div className="task-manager">
      <div className="task-manager-header">
        <h2>定时任务</h2>
        <div className="task-count">
          共 <span>{totalCount}</span> 个任务，<span>{enabledCount}</span> 个已启用
        </div>
      </div>

      <TaskCreator onCreate={handleCreateTask} isCreating={isCreating} />

      {error && (
        <div className="task-error">
          <span>{error}</span>
          <button onClick={loadTasks}>重试</button>
        </div>
      )}

      <TaskList
        tasks={tasks}
        isLoading={isLoading}
        onToggle={handleToggleTask}
        onDelete={handleDeleteTask}
      />
    </div>
  );
};

export default TaskManager;
