"""
iFlow 对话网页应用 - 会话路由

提供会话的 CRUD API：创建、查询、删除、更新标题
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.models.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
    ConversationDetailResponse,
    ConversationTitleUpdate,
    ConversationUpdateResponse,
    ConversationDeleteResponse,
    ChatMessageResponse,
    ErrorResponse,
)
from backend.services.auth import get_current_user
from backend.services.conversation_service import (
    ConversationService,
    conversation_to_response,
    chat_history_to_response,
)


router = APIRouter()


@router.get(
    "/",
    response_model=ConversationListResponse,
    responses={
        401: {"model": ErrorResponse},
    },
    summary="获取用户会话列表",
    description="获取当前用户的所有会话，按更新时间倒序排列"
)
async def get_conversations(
    limit: int = Query(50, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """
    获取用户会话列表
    
    - **limit**: 返回数量限制（1-100，默认50）
    - **offset**: 偏移量（用于分页）
    """
    service = ConversationService(db)
    conversations, total = await service.get_user_conversations(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    
    return ConversationListResponse(
        success=True,
        conversations=[conversation_to_response(c) for c in conversations],
        total=total,
    )


@router.post(
    "/",
    response_model=ConversationDetailResponse,
    responses={
        401: {"model": ErrorResponse},
    },
    summary="创建新会话",
    description="创建新会话，可选择性地提供首条消息用于生成标题"
)
async def create_conversation(
    data: Optional[ConversationCreate] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """
    创建新会话
    
    - **title**: 会话标题（可选，默认'新会话'）
    - **first_message**: 首条消息（可选，用于生成标题）
    
    如果提供 first_message 且未提供 title，将截取消息前20字符作为标题
    """
    service = ConversationService(db)
    
    # 处理空请求体
    title = data.title if data else None
    first_message = data.first_message if data else None
    
    conversation = await service.create_conversation(
        user_id=current_user.id,
        title=title,
        first_message=first_message,
    )
    
    return ConversationDetailResponse(
        success=True,
        conversation=conversation_to_response(conversation),
        messages=[],  # 新会话没有消息
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="获取会话详情",
    description="获取会话详情及其消息历史"
)
async def get_conversation(
    conversation_id: int,
    message_limit: int = Query(100, ge=1, le=500, description="消息数量限制"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """
    获取会话详情
    
    - **conversation_id**: 会话 ID
    - **message_limit**: 消息数量限制（1-500，默认100）
    """
    service = ConversationService(db)
    
    result = await service.get_conversation_with_messages(
        conversation_id=conversation_id,
        user_id=current_user.id,
        message_limit=message_limit,
    )
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问"
        )
    
    conversation, messages = result
    
    return ConversationDetailResponse(
        success=True,
        conversation=conversation_to_response(conversation),
        messages=[chat_history_to_response(m) for m in messages],
    )


@router.delete(
    "/{conversation_id}",
    response_model=ConversationDeleteResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="删除会话",
    description="删除会话及其所有消息"
)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDeleteResponse:
    """
    删除会话
    
    - **conversation_id**: 会话 ID
    
    删除会话将同时删除该会话下的所有消息
    """
    service = ConversationService(db)
    
    success = await service.delete_conversation(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问"
        )
    
    return ConversationDeleteResponse(
        success=True,
        message="会话删除成功",
    )


@router.put(
    "/{conversation_id}/title",
    response_model=ConversationUpdateResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="更新会话标题",
    description="更新会话标题"
)
async def update_conversation_title(
    conversation_id: int,
    data: ConversationTitleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationUpdateResponse:
    """
    更新会话标题
    
    - **conversation_id**: 会话 ID
    - **title**: 新标题（1-255字符）
    """
    service = ConversationService(db)
    
    conversation = await service.update_conversation_title(
        conversation_id=conversation_id,
        user_id=current_user.id,
        new_title=data.title,
    )
    
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问"
        )
    
    return ConversationUpdateResponse(
        success=True,
        conversation=conversation_to_response(conversation),
        message="标题更新成功",
    )
