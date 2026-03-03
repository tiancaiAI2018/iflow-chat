import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import TaskManager from './TaskManager';
import TaskList from './TaskList';
import TaskCreator from './TaskCreator';
import * as api from '../../services/api';

// Mock API
jest.mock('../../services/api');
const mockApiService = api.apiService as jest.Mocked<typeof api.apiService>;

// Mock useAuth
jest.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'test', email: 'test@test.com' },
    isAuthenticated: true,
    isLoading: false,
    logout: jest.fn(),
  }),
}));

const mockTasks = [
  {
    id: 'task-1',
    content: '查看股票',
    cron: '0 9 * * *',
    natural_language: '每天早上9点提醒我查看股票',
    enabled: true,
    created_at: '2026-03-03T10:00:00',
    last_run: '2026-03-03T09:00:00',
    next_run: '2026-03-04T09:00:00',
  },
  {
    id: 'task-2',
    content: '写周报',
    cron: '0 17 * * 5',
    natural_language: '每周五下午5点提醒我写周报',
    enabled: false,
    created_at: '2026-03-03T11:00:00',
    last_run: null,
    next_run: null,
  },
];

// Wrapper component
const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>{children}</BrowserRouter>
);

describe('TaskManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiService.getTasks.mockResolvedValue({ tasks: mockTasks });
  });

  test('renders task manager header', async () => {
    render(
      <Wrapper>
        <TaskManager />
      </Wrapper>
    );

    expect(screen.getByText('定时任务')).toBeInTheDocument();
    await waitFor(() => {
      expect(mockApiService.getTasks).toHaveBeenCalled();
    });
  });

  test('displays task count after loading', async () => {
    render(
      <Wrapper>
        <TaskManager />
      </Wrapper>
    );

    await waitFor(() => {
      const taskCountDiv = screen.getByText((content, element) => {
        return element?.classList.contains('task-count') || false;
      });
      expect(taskCountDiv).toBeInTheDocument();
      expect(taskCountDiv.textContent).toContain('共');
      expect(taskCountDiv.textContent).toContain('2');
      expect(taskCountDiv.textContent).toContain('1 个已启用');
    });
  });

  test('shows loading state initially', () => {
    mockApiService.getTasks.mockImplementation(() => new Promise(() => {}));

    render(
      <Wrapper>
        <TaskManager />
      </Wrapper>
    );

    expect(screen.getByText('加载任务列表...')).toBeInTheDocument();
  });

  test('creates a new task', async () => {
    const newTask = {
      id: 'task-3',
      content: '喝水',
      cron: '0 * * * *',
      natural_language: '每小时提醒我喝水',
      enabled: true,
      created_at: '2026-03-03T12:00:00',
      last_run: null,
      next_run: '2026-03-03T13:00:00',
    };

    mockApiService.createTask.mockResolvedValue({ success: true, task: newTask });

    render(
      <Wrapper>
        <TaskManager />
      </Wrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('查看股票')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/例如：每天早上9点/);
    fireEvent.change(input, { target: { value: '每小时提醒我喝水' } });

    const createButton = screen.getByText('创建任务');
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(mockApiService.createTask).toHaveBeenCalledWith({
        description: '每小时提醒我喝水',
      });
    });
  });
});

describe('TaskList', () => {
  const mockToggle = jest.fn();
  const mockDelete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders loading state', () => {
    render(<TaskList tasks={[]} isLoading={true} onToggle={mockToggle} onDelete={mockDelete} />);

    expect(screen.getByText('加载任务列表...')).toBeInTheDocument();
  });

  test('renders empty state', () => {
    render(<TaskList tasks={[]} isLoading={false} onToggle={mockToggle} onDelete={mockDelete} />);

    expect(screen.getByText('暂无定时任务')).toBeInTheDocument();
    expect(screen.getByText(/使用自然语言创建任务/)).toBeInTheDocument();
  });

  test('renders task list', () => {
    render(<TaskList tasks={mockTasks} isLoading={false} onToggle={mockToggle} onDelete={mockDelete} />);

    expect(screen.getByText('查看股票')).toBeInTheDocument();
    expect(screen.getByText('写周报')).toBeInTheDocument();
  });

  test('displays enabled task correctly', () => {
    render(<TaskList tasks={mockTasks} isLoading={false} onToggle={mockToggle} onDelete={mockDelete} />);

    const enabledButton = screen.getAllByRole('button')[0];
    expect(enabledButton).toHaveTextContent('✓ 启用');
  });

  test('displays disabled task correctly', () => {
    render(<TaskList tasks={mockTasks} isLoading={false} onToggle={mockToggle} onDelete={mockDelete} />);

    const disabledButton = screen.getAllByRole('button')[2];
    expect(disabledButton).toHaveTextContent('○ 禁用');
  });

  test('toggles task on click', async () => {
    mockToggle.mockResolvedValue(undefined);

    render(<TaskList tasks={mockTasks} isLoading={false} onToggle={mockToggle} onDelete={mockDelete} />);

    const toggleButton = screen.getAllByRole('button')[0];
    fireEvent.click(toggleButton);

    await waitFor(() => {
      expect(mockToggle).toHaveBeenCalledWith('task-1');
    });
  });

  test('deletes task with confirmation', async () => {
    window.confirm = jest.fn().mockReturnValue(true);
    mockDelete.mockResolvedValue(undefined);

    render(<TaskList tasks={mockTasks} isLoading={false} onToggle={mockToggle} onDelete={mockDelete} />);

    const deleteButton = screen.getAllByRole('button')[1];
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith('task-1');
    });
  });

  test('does not delete task if confirmation is cancelled', () => {
    window.confirm = jest.fn().mockReturnValue(false);

    render(<TaskList tasks={mockTasks} isLoading={false} onToggle={mockToggle} onDelete={mockDelete} />);

    const deleteButton = screen.getAllByRole('button')[1];
    fireEvent.click(deleteButton);

    expect(mockDelete).not.toHaveBeenCalled();
  });

  test('displays cron expression correctly', () => {
    render(<TaskList tasks={mockTasks} isLoading={false} onToggle={mockToggle} onDelete={mockDelete} />);

    expect(screen.getByText('每天 9:00')).toBeInTheDocument();
    expect(screen.getByText('每周五 17:00')).toBeInTheDocument();
  });

  test('displays last run and next run times', () => {
    render(<TaskList tasks={mockTasks} isLoading={false} onToggle={mockToggle} onDelete={mockDelete} />);

    expect(screen.getByText(/上次执行:/)).toBeInTheDocument();
    expect(screen.getByText(/下次执行:/)).toBeInTheDocument();
  });
});

describe('TaskCreator', () => {
  const mockCreate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders task creator form', () => {
    render(<TaskCreator onCreate={mockCreate} isCreating={false} />);

    expect(screen.getByText('创建定时任务')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/例如：每天早上9点/)).toBeInTheDocument();
    expect(screen.getByText('创建任务')).toBeInTheDocument();
  });

  test('displays example prompts', () => {
    render(<TaskCreator onCreate={mockCreate} isCreating={false} />);

    expect(screen.getByText('每天早上9点提醒我查看股票')).toBeInTheDocument();
    expect(screen.getByText('每周五下午5点提醒我写周报')).toBeInTheDocument();
  });

  test('fills input on example click', () => {
    render(<TaskCreator onCreate={mockCreate} isCreating={false} />);

    const exampleButton = screen.getByText('每天早上9点提醒我查看股票');
    fireEvent.click(exampleButton);

    const input = screen.getByPlaceholderText(/例如：每天早上9点/) as HTMLInputElement;
    expect(input.value).toBe('每天早上9点提醒我查看股票');
  });

  test('disables create button when input is empty', () => {
    render(<TaskCreator onCreate={mockCreate} isCreating={false} />);

    const createButton = screen.getByText('创建任务');
    expect(createButton).toBeDisabled();
    
    // 点击禁用按钮不会触发 onCreate
    fireEvent.click(createButton);
    expect(mockCreate).not.toHaveBeenCalled();
  });

  test('creates task on form submit', async () => {
    mockCreate.mockResolvedValue(undefined);

    render(<TaskCreator onCreate={mockCreate} isCreating={false} />);

    const input = screen.getByPlaceholderText(/例如：每天早上9点/);
    fireEvent.change(input, { target: { value: '每天早上8点提醒我' } });

    const form = input.closest('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith('每天早上8点提醒我');
    });
  });

  test('disables form when creating', () => {
    render(<TaskCreator onCreate={mockCreate} isCreating={true} />);

    const input = screen.getByPlaceholderText(/例如：每天早上9点/);
    expect(input).toBeDisabled();

    const createButton = screen.getByText('创建中...');
    expect(createButton).toBeDisabled();
  });

  test('clears input after successful creation', async () => {
    mockCreate.mockResolvedValue(undefined);

    render(<TaskCreator onCreate={mockCreate} isCreating={false} />);

    const input = screen.getByPlaceholderText(/例如：每天早上9点/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: '测试任务' } });

    const createButton = screen.getByText('创建任务');
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalled();
    });

    // Input should be cleared after successful creation
    await waitFor(() => {
      expect(input.value).toBe('');
    });
  });

  test('displays supported formats', () => {
    render(<TaskCreator onCreate={mockCreate} isCreating={false} />);

    expect(screen.getByText('支持的格式')).toBeInTheDocument();
    // 文本被拆分成多个元素，使用部分匹配
    expect(screen.getByText('每天', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText(/每天早上8点/)).toBeInTheDocument();
  });
});
