"""
iFlow 对话网页应用 - 认证路由

提供用户注册、登录、邮箱验证码、Token 刷新等认证相关 API
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.models.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    RegisterResponse,
    LoginResponse,
    SendCodeRequest,
    SendCodeResponse,
    VerifyCodeRequest,
    VerifyCodeResponse,
    MeResponse,
    ErrorResponse,
)
from backend.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    is_token_expired,
    should_refresh_token,
    refresh_access_token,
    get_token_info,
)
from backend.services.email_service import email_service

security = HTTPBearer()


router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="用户注册",
    description="使用用户名、邮箱和密码注册新用户"
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> RegisterResponse:
    """
    用户注册接口
    
    - **username**: 用户名（2-50字符）
    - **email**: 邮箱地址
    - **password**: 密码（至少6字符）
    """
    # 检查用户名是否已存在
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已被使用"
        )
    
    # 检查邮箱是否已存在
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已被注册"
        )
    
    # 创建用户
    hashed_password = hash_password(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # 生成 Token
    token = create_access_token({"sub": new_user.id, "username": new_user.username})
    
    return RegisterResponse(
        success=True,
        message="注册成功",
        token=token,
        user=UserResponse.model_validate(new_user)
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse},
    },
    summary="用户登录",
    description="使用用户名和密码登录"
)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    """
    用户登录接口
    
    - **username**: 用户名
    - **password**: 密码
    """
    # 查询用户
    result = await db.execute(
        select(User).where(User.username == credentials.username)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 验证密码
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 更新最后登录时间
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(user)
    
    # 生成 Token
    token = create_access_token({"sub": user.id, "username": user.username})
    
    return LoginResponse(
        success=True,
        token=token,
        user=UserResponse.model_validate(user)
    )


@router.post(
    "/send-code",
    response_model=SendCodeResponse,
    responses={
        429: {"model": ErrorResponse},
    },
    summary="发送验证码",
    description="发送邮箱验证码（1分钟限流）"
)
async def send_code(
    request: SendCodeRequest,
    db: AsyncSession = Depends(get_db)
) -> SendCodeResponse:
    """
    发送验证码接口
    
    - **email**: 邮箱地址
    
    验证码有效期为5分钟，发送频率限制为1分钟1次
    """
    success, message = await email_service.send_verification_code(db, request.email)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message
        )
    
    return SendCodeResponse(
        success=True,
        message=message
    )


@router.post(
    "/verify-code",
    response_model=VerifyCodeResponse,
    responses={
        400: {"model": ErrorResponse},
    },
    summary="验证码登录/注册",
    description="使用邮箱验证码登录或注册（新用户自动注册）"
)
async def verify_code(
    request: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db)
) -> VerifyCodeResponse:
    """
    验证码登录/注册接口
    
    - **email**: 邮箱地址
    - **code**: 6位验证码
    
    如果邮箱未注册，将自动创建新用户
    """
    # 验证验证码
    success, message = await email_service.verify_code(db, request.email, request.code)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # 查找用户
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    is_new_user = False
    
    if not user:
        # 新用户自动注册
        # 使用邮箱前缀作为默认用户名
        default_username = request.email.split("@")[0]
        
        # 检查用户名是否已存在，如果存在则添加随机后缀
        result = await db.execute(
            select(User).where(User.username == default_username)
        )
        if result.scalar_one_or_none():
            import random
            default_username = f"{default_username}_{random.randint(1000, 9999)}"
        
        # 创建用户（验证码登录用户没有密码）
        user = User(
            username=default_username,
            email=request.email,
            password_hash="",  # 验证码登录用户没有密码哈希
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        is_new_user = True
    else:
        # 更新最后登录时间
        user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        await db.refresh(user)
    
    # 生成 Token
    token = create_access_token({"sub": user.id, "username": user.username})
    
    return VerifyCodeResponse(
        success=True,
        token=token,
        user=UserResponse.model_validate(user),
        is_new_user=is_new_user,
        message="登录成功" if not is_new_user else "注册成功"
    )


@router.get(
    "/me",
    response_model=MeResponse,
    responses={
        401: {"model": ErrorResponse},
    },
    summary="获取当前用户信息",
    description="获取当前认证用户的详细信息"
)
async def get_me(
    current_user: User = Depends(get_current_user)
) -> MeResponse:
    """
    获取当前用户信息接口
    
    需要在 Header 中携带有效的 JWT Token:
    Authorization: Bearer <token>
    """
    return MeResponse(
        success=True,
        user=UserResponse.model_validate(current_user)
    )


@router.post(
    "/refresh",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse},
    },
    summary="刷新 Token",
    description="使用当前 Token 刷新获取新的 Token（Token 即将过期时使用）"
)
async def refresh_token(
    current_user: User = Depends(get_current_user)
) -> LoginResponse:
    """
    刷新 Token 接口
    
    需要在 Header 中携带有效的 JWT Token:
    Authorization: Bearer <token>
    
    - 如果 Token 已过期，将返回 401 错误
    - 如果 Token 有效，将返回新的 Token
    """
    # 生成新的 Token
    new_token = create_access_token({"sub": current_user.id, "username": current_user.username})
    
    return LoginResponse(
        success=True,
        token=new_token,
        user=UserResponse.model_validate(current_user)
    )


@router.get(
    "/token-info",
    summary="获取 Token 信息",
    description="获取当前 Token 的详细信息（有效期、是否需要刷新等）"
)
async def token_info(
    current_user: User = Depends(get_current_user),
    credentials = Depends(security),
):
    """
    获取 Token 详细信息接口
    
    返回 Token 的有效期、是否需要刷新等信息
    """
    from fastapi.security import HTTPBearer
    from backend.services.auth import get_token_info
    
    token = credentials.credentials
    info = get_token_info(token)
    
    return {
        "success": True,
        "token_info": info,
    }
