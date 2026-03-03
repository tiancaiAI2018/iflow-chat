"""
通知 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.auth import get_current_user
from backend.services.notification_store import get_notification_store
from backend.models.user import User
from backend.models.schemas import (
    NotificationListResponse,
    NotificationResponse,
    NotificationMarkReadResponse,
    NotificationDeleteResponse,
    NotificationMarkAllReadResponse,
)

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    unread_only: bool = Query(False, description="是否只获取未读通知"),
    limit: int = Query(50, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_user),
):
    """
    获取通知列表
    
    - **unread_only**: 是否只返回未读通知
    - **limit**: 返回数量限制，默认 50，最大 100
    - **offset**: 偏移量，用于分页
    """
    store = get_notification_store()
    result = store.get_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    
    # 转换为响应模型
    notifications = [
        NotificationResponse(
            id=n["id"],
            task_id=n.get("task_id"),
            content=n["content"],
            read=n.get("read", False),
            created_at=n["created_at"],
        )
        for n in result["notifications"]
    ]
    
    return NotificationListResponse(
        success=True,
        notifications=notifications,
        unread_count=result["unread_count"],
        total=result["total"],
    )


@router.put("/{notification_id}/read", response_model=NotificationMarkReadResponse)
async def mark_notification_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    标记通知为已读
    
    - **notification_id**: 通知 ID
    """
    store = get_notification_store()
    success = store.mark_as_read(
        user_id=current_user.id,
        notification_id=notification_id,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    return NotificationMarkReadResponse(
        success=True,
        message="已标记为已读",
    )


@router.put("/read-all", response_model=NotificationMarkAllReadResponse)
async def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
):
    """
    标记所有通知为已读
    """
    store = get_notification_store()
    count = store.mark_all_as_read(user_id=current_user.id)
    
    return NotificationMarkAllReadResponse(
        success=True,
        message=f"已标记 {count} 条通知为已读",
        count=count,
    )


@router.delete("/{notification_id}", response_model=NotificationDeleteResponse)
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    删除通知
    
    - **notification_id**: 通知 ID
    """
    store = get_notification_store()
    success = store.delete_notification(
        user_id=current_user.id,
        notification_id=notification_id,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    return NotificationDeleteResponse(
        success=True,
        message="通知已删除",
    )


@router.delete("", response_model=NotificationDeleteResponse)
async def clear_all_notifications(
    current_user: User = Depends(get_current_user),
):
    """
    清除所有通知
    """
    store = get_notification_store()
    count = store.clear_all(user_id=current_user.id)
    
    return NotificationDeleteResponse(
        success=True,
        message=f"已删除 {count} 条通知",
    )
