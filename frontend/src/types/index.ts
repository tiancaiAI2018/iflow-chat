// 用户相关类型
export interface User {
  id: number;
  username: string;
  email: string;
  created_at: string;
  last_login: string | null;
}

// 认证相关类型
export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  email: string;
}

export interface SendCodeRequest {
  email: string;
}

export interface VerifyCodeRequest {
  email: string;
  code: string;
}

export interface AuthResponse {
  success: boolean;
  message?: string;
  token?: string;
  user?: User;
  is_new_user?: boolean;
}

// 消息相关类型
export interface Message {
  id: number;
  user_id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface SendMessageRequest {
  content: string;
}

export interface ChatHistoryResponse {
  messages: Message[];
  total: number;
  page: number;
  page_size: number;
}

// 工具调用类型
export interface ToolCall {
  tool_id?: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  result?: unknown;
}

// WebSocket 消息类型
export type WSMessageType = 
  | 'chat'
  | 'auth'
  | 'ping'
  | 'assistant_message'
  | 'tool_call'
  | 'notification'
  | 'error'
  | 'cancel_result';

export interface WSMessage {
  type: WSMessageType;
  content?: string;
  is_delta?: boolean;
  is_finished?: boolean;
  tool_id?: string;
  tool_name?: string;
  arguments?: Record<string, unknown>;
  status?: ToolCall['status'];
  result?: unknown;
  notification?: Notification;
  message?: string;
  token?: string;
  success?: boolean;
}

// 定时任务类型
export interface Task {
  id: string;
  content: string;
  cron: string;
  natural_language: string;
  enabled: boolean;
  created_at: string;
  last_run: string | null;
  next_run: string | null;
}

export interface CreateTaskRequest {
  description: string;
}

export interface TasksResponse {
  tasks: Task[];
}

// 通知类型
export interface Notification {
  id: string;
  task_id: string | null;
  content: string;
  read: boolean;
  created_at: string;
}

export interface NotificationsResponse {
  notifications: Notification[];
  unread_count: number;
}

// 会话相关类型
export interface Conversation {
  id: number;
  user_id: number;
  title: string;
  iflow_session_id: string | null;
  working_directory: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationCreate {
  title?: string;
  first_message?: string;
  working_directory?: string;
}

export interface ConversationUpdate {
  title: string;
}

export interface ConversationResponse {
  id: number;
  user_id: number;
  title: string;
  iflow_session_id: string | null;
  working_directory: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  conversations: ConversationResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface ConversationDetailResponse {
  conversation: ConversationResponse;
  messages: Message[];
  total_messages: number;
}

// API 响应通用类型
export interface ApiResponse<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
}

// 目录相关类型
export interface DirectoryNode {
  name: string;
  path: string;
  children?: DirectoryNode[];
}

export interface DirectoryListResponse {
  success: boolean;
  directories: DirectoryNode[];
  root_path: string;
}

// ACP 端口相关类型
export interface ACPInfoResponse {
  user_id: number;
  ports: number[];
  current_port: number | null;
  total_ports: number;
  last_used: {
    port: number;
    cwd: string;
    timestamp: number;
  } | null;
}

export interface KillPortRequest {
  port: number;
}

export interface KillPortResponse {
  success: boolean;
  message: string;
  port: number;
}
