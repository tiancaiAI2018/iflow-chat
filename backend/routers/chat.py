"""
对话 API 路由
处理聊天消息发送和历史记录查询
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User, ChatHistory
from backend.models.schemas import ErrorResponse
from backend.services.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class SendMessageRequest(BaseModel):
    """发送消息请求模型"""
    content: str = Field(..., min_length=1, max_length=10000, description="消息内容")


class MessageItem(BaseModel):
    """消息项模型"""
    id: int
    role: str  # 'user' | 'assistant'
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class SendMessageResponse(BaseModel):
    """发送消息响应模型"""
    success: bool = True
    message: MessageItem
    message_text: str = "消息已保存"


class ChatHistoryResponse(BaseModel):
    """聊天历史响应模型"""
    success: bool = True
    messages: List[MessageItem]
    total: int
    page: int
    page_size: int
    has_more: bool


# ==================== API 端点 ====================

@router.post("", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    发送消息
    
    保存用户发送的消息到数据库。
    注意：此接口仅用于保存消息，实际的 AI 响应通过 WebSocket 获取。
    
    Args:
        request: 消息请求
        current_user: 当前登录用户
        db: 数据库会话
    
    Returns:
        SendMessageResponse: 包含保存的消息信息
    """
    # 创建消息记录
    chat_message = ChatHistory(
        user_id=current_user.id,
        role="user",
        content=request.content,
    )
    
    db.add(chat_message)
    await db.commit()
    await db.refresh(chat_message)
    
    logger.info(f"Message saved: user_id={current_user.id}, message_id={chat_message.id}")
    
    return SendMessageResponse(
        message=MessageItem(
            id=chat_message.id,
            role=chat_message.role,
            content=chat_message.content,
            created_at=chat_message.created_at,
        )
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    before_id: Optional[int] = Query(None, description="获取此 ID 之前的消息（用于向上翻页）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取聊天历史记录
    
    支持分页和游标两种方式加载历史消息：
    - 分页模式：使用 page 和 page_size 参数
    - 游标模式：使用 before_id 参数获取更早的消息
    
    Args:
        page: 页码（从 1 开始）
        page_size: 每页数量（默认 20，最大 100）
        before_id: 获取此 ID 之前的消息（游标分页）
        current_user: 当前登录用户
        db: 数据库会话
    
    Returns:
        ChatHistoryResponse: 包含消息列表和分页信息
    """
    # 构建基础查询
    base_query = select(ChatHistory).where(
        ChatHistory.user_id == current_user.id
    )
    
    # 游标分页：获取指定 ID 之前的消息
    if before_id:
        base_query = base_query.where(ChatHistory.id < before_id)
    
    # 按时间倒序排列
    base_query = base_query.order_by(desc(ChatHistory.created_at))
    
    # 查询总数
    count_query = select(ChatHistory.id).where(
        ChatHistory.user_id == current_user.id
    )
    if before_id:
        count_query = count_query.where(ChatHistory.id < before_id)
    
    from sqlalchemy import func
    total_result = await db.execute(
        select(func.count()).select_from(count_query.subquery())
    )
    total = total_result.scalar() or 0
    
    # 分页查询
    offset = (page - 1) * page_size if not before_id else 0
    paginated_query = base_query.offset(offset).limit(page_size + 1)
    
    result = await db.execute(paginated_query)
    messages = result.scalars().all()
    
    # 判断是否还有更多
    has_more = len(messages) > page_size
    if has_more:
        messages = messages[:page_size]
    
    # 转换为响应模型（按时间正序返回）
    message_items = [
        MessageItem(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
        )
        for msg in reversed(messages)  # 反转使消息按时间正序
    ]
    
    return ChatHistoryResponse(
        messages=message_items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.delete("/history", response_model=dict)
async def clear_chat_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    清空聊天历史
    
    删除当前用户的所有聊天记录
    
    Args:
        current_user: 当前登录用户
        db: 数据库会话
    
    Returns:
        dict: 操作结果
    """
    # 删除该用户的所有聊天记录
    from sqlalchemy import delete
    
    stmt = delete(ChatHistory).where(ChatHistory.user_id == current_user.id)
    result = await db.execute(stmt)
    await db.commit()
    
    deleted_count = result.rowcount
    logger.info(f"Chat history cleared: user_id={current_user.id}, deleted={deleted_count}")
    
    return {
        "success": True,
        "message": f"已清空 {deleted_count} 条聊天记录",
        "deleted_count": deleted_count,
    }
