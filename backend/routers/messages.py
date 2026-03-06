"""
待消费消息 API 路由

用于 WebSocket 断线重连后恢复消息。

核心功能：
- 获取用户在 Redis 中待消费的消息（用于重连恢复）
- 消费用户消息（读取后删除）
"""
import json
import logging
from typing import Optional, TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from backend.models.user import User
from backend.models.schemas import (
    PendingMessagesResponse,
    PendingMessageItem,
    ErrorResponse,
)
from backend.services.auth import get_current_user

if TYPE_CHECKING:
    from backend.services.message_buffer import MessageBuffer

logger = logging.getLogger(__name__)

router = APIRouter()


def get_message_buffer_dep() -> "MessageBuffer":
    """依赖注入：获取 MessageBuffer 实例"""
    # 延迟导入避免循环依赖
    from backend.main import get_message_buffer
    return get_message_buffer()


@router.get(
    "/pending",
    response_model=PendingMessagesResponse,
    responses={401: {"model": ErrorResponse}},
)
async def get_pending_messages(
    count: int = Query(50, ge=1, le=100, description="最大获取数量"),
    current_user: User = Depends(get_current_user),
    message_buffer: "MessageBuffer" = Depends(get_message_buffer_dep),
):
    """
    获取待消费消息（用于断线重连恢复）

    从 Redis Stream 中获取用户未消费的消息，不删除消息。

    Args:
        count: 最大获取数量（默认 50，最大 100）
        current_user: 当前登录用户

    Returns:
        PendingMessagesResponse: 包含待消费消息列表

    Example:
        # WebSocket 重连后调用
        GET /api/messages/pending?count=50

        # 响应格式
        {
            "success": true,
            "messages": [
                {
                    "entry_id": "1234567890123-0",
                    "type": "stream",
                    "content": "Hello",
                    "is_delta": true,
                    "conversation_id": 1
                }
            ],
            "count": 1,
            "message": "获取成功"
        }
    """
    user_id = current_user.id

    try:
        # 从 Redis 获取待推送消息（不删除）
        pending = await message_buffer.get_pending(user_id=user_id, count=count)

        if not pending:
            return PendingMessagesResponse(
                messages=[],
                count=0,
                message="无待消费消息",
            )

        # 解析消息
        messages: list[PendingMessageItem] = []
        for stream_name, entries in pending:
            for entry_id, fields in entries:
                try:
                    data = json.loads(fields.get("data", "{}"))
                    messages.append(PendingMessageItem(
                        entry_id=entry_id,
                        type=data.get("type", "unknown"),
                        content=data.get("content", ""),
                        is_delta=data.get("is_delta"),
                        conversation_id=data.get("conversation_id"),
                        created_at=data.get("created_at"),
                    ))
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse message {entry_id}: {e}")
                    continue

        logger.info(f"Got {len(messages)} pending messages for user {user_id}")

        return PendingMessagesResponse(
            messages=messages,
            count=len(messages),
            message=f"获取成功，共 {len(messages)} 条消息",
        )

    except Exception as e:
        logger.error(f"Failed to get pending messages for user {user_id}: {e}")
        return PendingMessagesResponse(
            messages=[],
            count=0,
            message=f"获取消息失败: {str(e)}",
        )


@router.post(
    "/consume",
    response_model=PendingMessagesResponse,
    responses={401: {"model": ErrorResponse}},
)
async def consume_messages(
    count: int = Query(10, ge=1, le=100, description="最大消费数量"),
    current_user: User = Depends(get_current_user),
    message_buffer: "MessageBuffer" = Depends(get_message_buffer_dep),
):
    """
    消费待推送消息（读取后删除）

    从 Redis Stream 中消费用户的消息，读取后删除。

    Args:
        count: 最大消费数量（默认 10，最大 100）
        current_user: 当前登录用户

    Returns:
        PendingMessagesResponse: 包含消费的消息列表
    """
    user_id = current_user.id

    try:
        # 从 Redis 消费消息（读取后删除）
        consumed = await message_buffer.consume(user_id=user_id, count=count)

        if not consumed:
            return PendingMessagesResponse(
                messages=[],
                count=0,
                message="无待消费消息",
            )

        # 解析消息
        messages: list[PendingMessageItem] = []
        for stream_name, entries in consumed:
            for entry_id, fields in entries:
                try:
                    data = json.loads(fields.get("data", "{}"))
                    messages.append(PendingMessageItem(
                        entry_id=entry_id,
                        type=data.get("type", "unknown"),
                        content=data.get("content", ""),
                        is_delta=data.get("is_delta"),
                        conversation_id=data.get("conversation_id"),
                        created_at=data.get("created_at"),
                    ))
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse message {entry_id}: {e}")
                    continue

        logger.info(f"Consumed {len(messages)} messages for user {user_id}")

        return PendingMessagesResponse(
            messages=messages,
            count=len(messages),
            message=f"消费成功，共 {len(messages)} 条消息",
        )

    except Exception as e:
        logger.error(f"Failed to consume messages for user {user_id}: {e}")
        return PendingMessagesResponse(
            messages=[],
            count=0,
            message=f"消费消息失败: {str(e)}",
        )
