"""
iFlow 对话网页应用 - JWT 认证服务

提供 JWT Token 生成/验证和密码哈希/验证功能
包含 Token 过期检测和刷新支持
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.database import get_db
from backend.models.user import User


# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer 认证方案
security = HTTPBearer()

# Token 刷新阈值（分钟）- Token 过期前多少分钟可以刷新
TOKEN_REFRESH_THRESHOLD_MINUTES = 5


def hash_password(password: str) -> str:
    """
    使用 bcrypt 对密码进行哈希
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码字符串
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否匹配
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
        
    Returns:
        密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建 JWT Access Token
    
    Args:
        data: 要编码的数据（通常包含 user_id, username 等）
        expires_delta: 过期时间增量，如果不指定则使用默认配置
        
    Returns:
        JWT Token 字符串
    """
    to_encode = data.copy()
    
    # JWT sub claim 必须是字符串
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码并验证 JWT Token
    
    Args:
        token: JWT Token 字符串
        
    Returns:
        解码后的 payload 字典，如果验证失败返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        # 将 sub 转换回整数（如果可能）
        if "sub" in payload:
            try:
                payload["sub"] = int(payload["sub"])
            except (ValueError, TypeError):
                pass
        return payload
    except JWTError:
        return None


def is_token_expired(token: str) -> bool:
    """
    检查 Token 是否已过期
    
    Args:
        token: JWT Token 字符串
        
    Returns:
        bool: 是否已过期
    """
    payload = decode_access_token(token)
    if payload is None:
        return True
    
    if "exp" not in payload:
        return True
    
    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    return datetime.now(timezone.utc) > exp_time


def should_refresh_token(token: str) -> bool:
    """
    检查 Token 是否需要刷新（即将过期）
    
    Args:
        token: JWT Token 字符串
        
    Returns:
        bool: 是否需要刷新
    """
    payload = decode_access_token(token)
    if payload is None:
        return True
    
    if "exp" not in payload:
        return True
    
    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    
    # 如果 Token 将在阈值时间内过期，则需要刷新
    return (exp_time - now) < timedelta(minutes=TOKEN_REFRESH_THRESHOLD_MINUTES)


def refresh_access_token(token: str) -> Optional[str]:
    """
    刷新 Token
    
    如果 Token 有效但即将过期，生成新的 Token
    
    Args:
        token: 旧的 JWT Token 字符串
        
    Returns:
        新的 JWT Token 字符串，如果旧 Token 无效返回 None
    """
    payload = decode_access_token(token)
    if payload is None:
        return None
    
    # 检查是否已过期（过期的 Token 不能刷新）
    if is_token_expired(token):
        return None
    
    # 提取用户信息
    user_id = payload.get("sub")
    username = payload.get("username")
    
    if user_id is None:
        return None
    
    # 生成新的 Token
    new_token_data = {"sub": user_id}
    if username:
        new_token_data["username"] = username
    
    return create_access_token(new_token_data)


def get_token_remaining_time(token: str) -> Optional[timedelta]:
    """
    获取 Token 剩余有效时间
    
    Args:
        token: JWT Token 字符串
        
    Returns:
        timedelta: 剩余时间，如果 Token 无效返回 None
    """
    payload = decode_access_token(token)
    if payload is None:
        return None
    
    if "exp" not in payload:
        return None
    
    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    
    remaining = exp_time - now
    return remaining if remaining > timedelta(0) else timedelta(0)


def get_token_info(token: str) -> Dict[str, Any]:
    """
    获取 Token 详细信息
    
    Args:
        token: JWT Token 字符串
        
    Returns:
        Dict: Token 信息
    """
    payload = decode_access_token(token)
    
    if payload is None:
        return {
            "valid": False,
            "expired": True,
            "should_refresh": False,
        }
    
    expired = is_token_expired(token)
    remaining = get_token_remaining_time(token)
    
    return {
        "valid": not expired,
        "expired": expired,
        "should_refresh": should_refresh_token(token) and not expired,
        "remaining_seconds": remaining.total_seconds() if remaining else 0,
        "user_id": payload.get("sub"),
        "username": payload.get("username"),
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前认证用户的依赖项
    
    从 Authorization header 中提取 Token，验证并返回用户对象
    
    Args:
        credentials: HTTP Bearer 凭证
        db: 数据库会话
        
    Returns:
        当前用户对象
        
    Raises:
        HTTPException: Token 无效或用户不存在
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id: Optional[int] = payload.get("sub")
    
    if user_id is None:
        raise credentials_exception
    
    # 查询用户
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    可选的用户认证依赖项
    
    如果提供了有效的 Token 则返回用户，否则返回 None
    
    Args:
        credentials: HTTP Bearer 凭证（可选）
        db: 数据库会话
        
    Returns:
        当前用户对象或 None
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        return None
    
    user_id: Optional[int] = payload.get("sub")
    
    if user_id is None:
        return None
    
    # 查询用户
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    return user
