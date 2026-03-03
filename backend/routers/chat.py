"""
对话 API 路由
处理聊天消息发送和历史记录查询
优化大量消息的分页加载
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
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
    total_pages: Optional[int] = None  # 总页数（可选）
    first_message_id: Optional[int] = None  # 第一条消息ID（用于游标）
    last_message_id: Optional[int] = None  # 最后一条消息ID（用于游标）


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
    after_id: Optional[int] = Query(None, description="获取此 ID 之后的消息（用于向下翻页）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取聊天历史记录
    
    支持分页和游标两种方式加载历史消息：
    - 分页模式：使用 page 和 page_size 参数
    - 游标模式：使用 before_id 或 after_id 参数
    
    优化：
    - 支持大量消息的高效分页
    - 游标分页避免深分页性能问题
    - 返回总页数和边界消息ID
    
    Args:
        page: 页码（从 1 开始）
        page_size: 每页数量（默认 20，最大 100）
        before_id: 获取此 ID 之前的消息（向上翻页）
        after_id: 获取此 ID 之后的消息（向下翻页）
        current_user: 当前登录用户
        db: 数据库会话
    
    Returns:
        ChatHistoryResponse: 包含消息列表和分页信息
    """
    # 构建基础查询 - 只查询当前用户的消息
    base_query = select(ChatHistory).where(
        ChatHistory.user_id == current_user.id
    )
    
    # 游标分页：获取指定 ID 之前/之后的消息
    if before_id:
        base_query = base_query.where(ChatHistory.id < before_id)
    elif after_id:
        base_query = base_query.where(ChatHistory.id > after_id)
    
    # 查询总数（优化：使用 COUNT 而不是加载所有记录）
    count_query = select(func.count(ChatHistory.id)).where(
        ChatHistory.user_id == current_user.id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 计算总页数
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    
    # 游标分页模式
    if before_id or after_id:
        if before_id:
            # 向上翻页：获取更早的消息，按时间倒序
            paginated_query = base_query.order_by(desc(ChatHistory.created_at)).limit(page_size + 1)
        else:
            # 向下翻页：获取更新的消息，按时间正序
            paginated_query = base_query.order_by(ChatHistory.created_at).limit(page_size + 1)
        
        result = await db.execute(paginated_query)
        messages = result.scalars().all()
        
        # 判断是否还有更多
        has_more = len(messages) > page_size
        if has_more:
            messages = messages[:page_size]
        
        # 按时间正序返回
        message_items = [
            MessageItem(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
            )
            for msg in (reversed(messages) if before_id else messages)
        ]
    else:
        # 传统分页模式
        # 按时间倒序排列
        base_query = base_query.order_by(desc(ChatHistory.created_at))
        
        # 分页查询
        offset = (page - 1) * page_size
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
    
    # 获取边界消息ID
    first_message_id = message_items[0].id if message_items else None
    last_message_id = message_items[-1].id if message_items else None
    
    return ChatHistoryResponse(
        messages=message_items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
        total_pages=total_pages,
        first_message_id=first_message_id,
        last_message_id=last_message_id,
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
