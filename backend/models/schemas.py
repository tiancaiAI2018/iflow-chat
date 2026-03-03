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
