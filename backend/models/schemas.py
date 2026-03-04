"""
iFlow 对话网页应用 - Pydantic 请求/响应模型
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ==================== 用户相关 ====================

class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")


class UserCreate(UserBase):
    """用户注册请求模型"""
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class UserLogin(BaseModel):
    """用户登录请求模型"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户信息响应模型"""
    id: int
    username: str
    email: str
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== 认证相关 ====================

class TokenResponse(BaseModel):
    """Token 响应模型"""
    success: bool = True
    token: str
    user: Optional[UserResponse] = None
    message: Optional[str] = None


class RegisterResponse(BaseModel):
    """注册响应模型"""
    success: bool = True
    message: str = "注册成功"
    token: Optional[str] = None
    user: Optional[UserResponse] = None


class LoginResponse(BaseModel):
    """登录响应模型"""
    success: bool = True
    token: str
    user: UserResponse


class SendCodeRequest(BaseModel):
    """发送验证码请求模型"""
    email: EmailStr = Field(..., description="邮箱地址")


class SendCodeResponse(BaseModel):
    """发送验证码响应模型"""
    success: bool
    message: str


class VerifyCodeRequest(BaseModel):
    """验证码登录/注册请求模型"""
    email: EmailStr = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, description="6位验证码")


class VerifyCodeResponse(BaseModel):
    """验证码登录/注册响应模型"""
    success: bool
    token: Optional[str] = None
    user: Optional[UserResponse] = None
    is_new_user: bool = False
    message: str


class MeResponse(BaseModel):
    """获取当前用户信息响应模型"""
    success: bool = True
    user: UserResponse


class ErrorResponse(BaseModel):
    """错误响应模型"""
    success: bool = False
    message: str
    detail: Optional[str] = None


# ==================== 定时任务相关 ====================

class TaskCreate(BaseModel):
    """创建任务请求模型"""
    description: str = Field(..., min_length=1, max_length=500, description="自然语言描述")


class TaskResponse(BaseModel):
    """任务响应模型"""
    id: str
    user_id: int
    content: str
    cron: str
    natural_language: str
    enabled: bool
    created_at: str
    last_run: Optional[str] = None
    next_run: Optional[str] = None


class TaskListResponse(BaseModel):
    """任务列表响应模型"""
    success: bool = True
    tasks: list[TaskResponse]


class TaskCreateResponse(BaseModel):
    """创建任务响应模型"""
    success: bool = True
    task: TaskResponse
    message: str = "任务创建成功"


class TaskDeleteResponse(BaseModel):
    """删除任务响应模型"""
    success: bool = True
    message: str = "任务删除成功"


class TaskToggleResponse(BaseModel):
    """切换任务状态响应模型"""
    success: bool = True
    task: TaskResponse
    message: str


# ==================== 通知相关 ====================

class NotificationResponse(BaseModel):
    """通知响应模型"""
    id: str
    task_id: Optional[str] = None
    content: str
    read: bool = False
    created_at: str


class NotificationListResponse(BaseModel):
    """通知列表响应模型"""
    success: bool = True
    notifications: list[NotificationResponse]
    unread_count: int = 0
    total: int = 0


class NotificationMarkReadResponse(BaseModel):
    """标记已读响应模型"""
    success: bool = True
    message: str


class NotificationMarkAllReadResponse(BaseModel):
    """标记全部已读响应模型"""
    success: bool = True
    message: str
    count: int = 0


class NotificationDeleteResponse(BaseModel):
    """删除通知响应模型"""
    success: bool = True
    message: str


# ==================== 会话相关 ====================

class ConversationCreate(BaseModel):
    """创建会话请求模型"""
    title: Optional[str] = Field(None, max_length=255, description="会话标题（可选，默认'新会话'）")
    first_message: Optional[str] = Field(None, max_length=2000, description="首条消息（用于 AI 生成标题）")


class ConversationResponse(BaseModel):
    """会话响应模型"""
    id: int
    user_id: int
    title: str
    iflow_session_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """会话列表响应模型"""
    success: bool = True
    conversations: list[ConversationResponse]
    total: int = 0


class ConversationDetailResponse(BaseModel):
    """会话详情响应模型（包含消息历史）"""
    success: bool = True
    conversation: ConversationResponse
    messages: list["ChatMessageResponse"]


class ChatMessageResponse(BaseModel):
    """聊天消息响应模型"""
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationTitleUpdate(BaseModel):
    """更新会话标题请求模型"""
    title: str = Field(..., min_length=1, max_length=255, description="新标题")


class ConversationUpdateResponse(BaseModel):
    """更新会话标题响应模型"""
    success: bool = True
    conversation: ConversationResponse
    message: str = "标题更新成功"


class ConversationDeleteResponse(BaseModel):
    """删除会话响应模型"""
    success: bool = True
    message: str = "会话删除成功"


# 更新 forward reference
ConversationDetailResponse.model_rebuild()
