import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  User,
  LoginRequest,
  RegisterRequest,
  SendCodeRequest,
  VerifyCodeRequest,
  AuthResponse,
  SendMessageRequest,
  ChatHistoryResponse,
  Message,
  CreateTaskRequest,
  TasksResponse,
  Task,
  NotificationsResponse,
  Notification,
} from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // 请求拦截器：自动添加 Token
    this.api.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // 响应拦截器：处理 401 错误
    this.api.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // ========== 认证相关 ==========

  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await this.api.post<AuthResponse>('/auth/register', data);
    return response.data;
  }

  async login(data: LoginRequest): Promise<AuthResponse> {
    const response = await this.api.post<AuthResponse>('/auth/login', data);
    return response.data;
  }

  async sendCode(data: SendCodeRequest): Promise<AuthResponse> {
    const response = await this.api.post<AuthResponse>('/auth/send-code', data);
    return response.data;
  }

  async verifyCode(data: VerifyCodeRequest): Promise<AuthResponse> {
    const response = await this.api.post<AuthResponse>('/auth/verify-code', data);
    return response.data;
  }

  async getCurrentUser(): Promise<{ success: boolean; user: User }> {
    const response = await this.api.get<{ success: boolean; user: User }>('/auth/me');
    return response.data;
  }

  // ========== 对话相关 ==========

  async sendMessage(data: SendMessageRequest): Promise<{ success: boolean; message: Message }> {
    const response = await this.api.post<{ success: boolean; message: Message }>('/chat', data);
    return response.data;
  }

  async getChatHistory(params?: {
    page?: number;
    page_size?: number;
    before_id?: number;
  }): Promise<ChatHistoryResponse> {
    const response = await this.api.get<ChatHistoryResponse>('/chat/history', { params });
    return response.data;
  }

  async clearChatHistory(): Promise<{ success: boolean }> {
    const response = await this.api.delete<{ success: boolean }>('/chat/history');
    return response.data;
  }

  // ========== 定时任务相关 ==========

  async getTasks(): Promise<TasksResponse> {
    const response = await this.api.get<TasksResponse>('/tasks');
    return response.data;
  }

  async createTask(data: CreateTaskRequest): Promise<{ success: boolean; task: Task }> {
    const response = await this.api.post<{ success: boolean; task: Task }>('/tasks', data);
    return response.data;
  }

  async deleteTask(taskId: string): Promise<{ success: boolean }> {
    const response = await this.api.delete<{ success: boolean }>(`/tasks/${taskId}`);
    return response.data;
  }

  async toggleTask(taskId: string): Promise<{ success: boolean; enabled: boolean }> {
    const response = await this.api.put<{ success: boolean; enabled: boolean }>(
      `/tasks/${taskId}/toggle`
    );
    return response.data;
  }

  // ========== 通知相关 ==========

  async getNotifications(params?: {
    unread_only?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<NotificationsResponse> {
    const response = await this.api.get<NotificationsResponse>('/notifications', { params });
    return response.data;
  }

  async markNotificationAsRead(notificationId: string): Promise<{ success: boolean }> {
    const response = await this.api.put<{ success: boolean }>(
      `/notifications/${notificationId}/read`
    );
    return response.data;
  }

  async markAllNotificationsAsRead(): Promise<{ success: boolean }> {
    const response = await this.api.put<{ success: boolean }>('/notifications/read-all');
    return response.data;
  }

  async deleteNotification(notificationId: string): Promise<{ success: boolean }> {
    const response = await this.api.delete<{ success: boolean }>(
      `/notifications/${notificationId}`
    );
    return response.data;
  }

  async clearAllNotifications(): Promise<{ success: boolean }> {
    const response = await this.api.delete<{ success: boolean }>('/notifications');
    return response.data;
  }

  // ========== WebSocket ==========

  getWebSocketUrl(userId: number): string {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = process.env.REACT_APP_WS_HOST || 'localhost:8000';
    const token = localStorage.getItem('token');
    return `${wsProtocol}//${wsHost}/ws/${userId}?token=${token}`;
  }
}

// 导出单例
export const apiService = new ApiService();
export default apiService;
