"""
WebSocket 路由
处理 WebSocket 连接、消息路由、认证验证
支持定时任务意图识别和自动创建
集成 EventBus 实现输入输出解耦
"""
import asyncio
import logging
import json
from typing import Optional, Any, Tuple, Set
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.websocket_manager import (
    WebSocketManager,
    get_websocket_manager,
    ConnectionStatus,
)
from backend.services.auth import decode_access_token
from backend.services.iflow_client import (
    IFlowClientService,
    get_iflow_client,
    MessageType as IFlowMessageType,
    extract_task_intent,
    remove_task_json_from_response,
)
from backend.services.scheduler import get_scheduler
from backend.services.task_parser import get_task_parser
from backend.services.conversation_service import ConversationService
from backend.database import get_db
from backend.models.user import User, ChatHistory, Conversation
from sqlalchemy import select

# EventBus 相关导入
from backend.services.event_bus import EventBus
from backend.services.input_handlers.websocket_input import WebSocketInputHandler
from backend.services.message_buffer import MessageBuffer
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 消息模型 ====================

class WSMessage(BaseModel):
    """WebSocket 消息基类"""
    type: str


class ChatMessage(WSMessage):
    """聊天消息"""
    type: str = "chat"
    content: str
    conversation_id: Optional[int] = None  # 会话 ID（可选，用于切换会话）


class AuthMessage(WSMessage):
    """认证消息"""
    type: str = "auth"
    token: str


class PingMessage(WSMessage):
    """心跳消息"""
    type: str = "ping"


class SwitchConversationMessage(WSMessage):
    """切换会话消息"""
    type: str = "switch_conversation"
    conversation_id: int


# ==================== 响应模型 ====================

class WSResponse(BaseModel):
    """WebSocket 响应基类"""
    type: str
    timestamp: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        self.timestamp = datetime.now().isoformat()


class AuthSuccessResponse(WSResponse):
    """认证成功响应"""
    type: str = "auth_success"
    user_id: int
    username: str


class AuthFailedResponse(WSResponse):
    """认证失败响应"""
    type: str = "auth_failed"
    message: str


class PongResponse(WSResponse):
    """心跳响应"""
    type: str = "pong"


class AssistantMessageResponse(WSResponse):
    """助手消息响应"""
    type: str = "assistant_message"
    content: str
    is_delta: bool = True
    is_finished: bool = False


class ToolCallResponse(WSResponse):
    """工具调用响应"""
    type: str = "tool_call"
    tool_id: Optional[str] = None  # 工具调用 ID，用于前端更新状态
    tool_name: str
    arguments: dict = {}
    status: str  # pending, in_progress, completed, failed
    result: Optional[Any] = None  # 可以是 dict、str 或其他类型
    error: Optional[str] = None


class NotificationResponse(WSResponse):
    """通知推送响应"""
    type: str = "notification"
    notification: dict


class ErrorResponse(WSResponse):
    """错误响应"""
    type: str = "error"
    message: str
    code: Optional[str] = None


class ConnectionStatusResponse(WSResponse):
    """连接状态响应"""
    type: str = "connection_status"
    status: str
    message: str


class ConversationSwitchedResponse(WSResponse):
    """会话切换响应"""
    type: str = "conversation_switched"
    conversation_id: int
    title: str
    iflow_session_id: Optional[str] = None


# ==================== Redis 消息订阅辅助函数 ====================

async def subscribe_redis_messages(
    websocket: WebSocket,
    user_id: int,
    message_buffer: MessageBuffer,
    stop_event: asyncio.Event,
    processed_ids: Set[str],
    conversation_id: Optional[int] = None,
):
    """
    订阅 Redis Stream 消息并推送给 WebSocket

    Args:
        websocket: WebSocket 连接
        user_id: 用户 ID
        message_buffer: 消息缓冲服务
        stop_event: 停止信号
        processed_ids: 已处理的消息 ID 集合
        conversation_id: 当前会话 ID（可选，用于过滤消息）
    """
    logger.debug(f"Starting Redis subscription for user {user_id}")

    while not stop_event.is_set():
        try:
            # 从 Redis Stream 获取待推送消息
            pending = await message_buffer.get_pending(user_id, count=10)

            if pending:
                for stream_name, entries in pending:
                    for entry_id, fields in entries:
                        # 跳过已处理的消息
                        if entry_id in processed_ids:
                            continue

                        # 标记为已处理
                        processed_ids.add(entry_id)

                        # 解析消息
                        try:
                            data = json.loads(fields.get('data', '{}'))
                        except json.JSONDecodeError:
                            continue

                        # 过滤会话 ID（如果指定）
                        msg_conversation_id = data.get('conversation_id')
                        if conversation_id is not None and msg_conversation_id is not None:
                            if msg_conversation_id != conversation_id:
                                continue

                        # 推送给 WebSocket
                        msg_type = data.get('type')

                        if msg_type == 'stream':
                            # 流式响应
                            await websocket.send_json(
                                AssistantMessageResponse(
                                    content=data.get('content', ''),
                                    is_delta=data.get('is_delta', True),
                                    is_finished=False,
                                ).model_dump()
                            )

                        elif msg_type == 'complete':
                            # 完成响应
                            await websocket.send_json(
                                AssistantMessageResponse(
                                    content='',
                                    is_delta=False,
                                    is_finished=True,
                                ).model_dump()
                            )
                            # 消费已处理的消息
                            await message_buffer.consume(user_id, count=len(processed_ids))

            # 短暂等待
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in Redis subscription: {e}")
            await asyncio.sleep(1)

    logger.debug(f"Redis subscription stopped for user {user_id}")


# ==================== WebSocket 端点 ====================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    token: Optional[str] = Query(None),
    manager: WebSocketManager = Depends(get_websocket_manager),
):
    """
    WebSocket 连接端点

    连接流程：
    1. 客户端连接 WebSocket
    2. 可选：通过 query 参数传递 token 进行认证
    3. 或：连接后发送 auth 消息进行认证
    4. 认证成功后可以发送 chat 消息
    5. 服务器返回 assistant_message、tool_call 等消息

    消息格式：
    - 认证：{"type": "auth", "token": "xxx"}
    - 聊天：{"type": "chat", "content": "你好"}
    - 心跳：{"type": "ping"}
    """
    # 接受连接
    await websocket.accept()

    # 注册连接
    conn_info = await manager.connect(websocket, user_id)
    connection_id = conn_info.connection_id

    logger.info(f"WebSocket connection established: user_id={user_id}, connection_id={connection_id}")

    # 发送连接状态
    await websocket.send_json(
        ConnectionStatusResponse(
            status="connected",
            message="WebSocket connected, please authenticate"
        ).model_dump()
    )

    # 如果 query 参数中有 token，尝试认证
    if token:
        authenticated = await authenticate_connection(
            websocket, manager, connection_id, user_id, token
        )
        if not authenticated:
            await manager.disconnect(connection_id)
            return

    # 用户数据库会话
    db_gen = get_db()
    db = await anext(db_gen)

    # 从 WebSocketManager 获取或创建用户的 iFlow session
    user_session = manager.get_or_create_user_session(user_id)
    iflow_client = user_session.iflow_client

    # 当前会话 ID（用于消息关联）
    current_conversation_id: Optional[int] = None

    # EventBus 相关组件
    input_handler = WebSocketInputHandler(sender=f"ws:{connection_id}")
    message_buffer = MessageBuffer(
        redis_url=settings.REDIS_URL,
        ttl=settings.REDIS_MESSAGE_TTL,
    )

    # Redis 订阅相关
    redis_stop_event = asyncio.Event()
    redis_task: Optional[asyncio.Task] = None
    processed_ids: Set[str] = set()

    try:
        # 消息循环
        while True:
            # 接收消息
            try:
                raw_data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=300.0  # 5分钟超时
                )
            except asyncio.TimeoutError:
                logger.warning(f"WebSocket timeout: connection_id={connection_id}")
                await websocket.send_json(
                    ErrorResponse(
                        message="Connection timeout",
                        code="TIMEOUT"
                    ).model_dump()
                )
                break

            # 解析消息
            try:
                data = json.loads(raw_data)
                msg_type = data.get("type")
            except json.JSONDecodeError:
                await websocket.send_json(
                    ErrorResponse(
                        message="Invalid JSON format",
                        code="INVALID_JSON"
                    ).model_dump()
                )
                continue

            # 处理不同类型的消息
            if msg_type == "auth":
                # 认证消息
                token = data.get("token")
                if token:
                    await authenticate_connection(
                        websocket, manager, connection_id, user_id, token
                    )
                else:
                    await websocket.send_json(
                        AuthFailedResponse(message="Token required").model_dump()
                    )

            elif msg_type == "ping":
                # 心跳消息
                await websocket.send_json(PongResponse().model_dump())

            elif msg_type == "switch_conversation":
                # 切换会话消息
                if not manager.is_authenticated(connection_id):
                    await websocket.send_json(
                        ErrorResponse(
                            message="Please authenticate first",
                            code="NOT_AUTHENTICATED"
                        ).model_dump()
                    )
                    continue

                conversation_id = data.get("conversation_id")
                if not conversation_id:
                    await websocket.send_json(
                        ErrorResponse(
                            message="conversation_id required",
                            code="MISSING_CONVERSATION_ID"
                        ).model_dump()
                    )
                    continue

                # 处理会话切换
                current_conversation_id, iflow_client = await handle_switch_conversation(
                    websocket=websocket,
                    manager=manager,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    db=db,
                    current_conversation_id=current_conversation_id,
                    iflow_client=iflow_client,
                )

            elif msg_type == "chat":
                # 聊天消息
                if not manager.is_authenticated(connection_id):
                    await websocket.send_json(
                        ErrorResponse(
                            message="Please authenticate first",
                            code="NOT_AUTHENTICATED"
                        ).model_dump()
                    )
                    continue

                content = data.get("content", "")
                if not content.strip():
                    continue

                # 获取消息中的 conversation_id（可选，用于首次指定会话）
                message_conversation_id = data.get("conversation_id")

                # 处理聊天消息（使用 EventBus）
                current_conversation_id, iflow_client = await handle_chat_message_eventbus(
                    websocket=websocket,
                    manager=manager,
                    connection_id=connection_id,
                    user_id=user_id,
                    content=content,
                    db=db,
                    iflow_client=iflow_client,
                    input_handler=input_handler,
                    message_buffer=message_buffer,
                    current_conversation_id=message_conversation_id or current_conversation_id,
                    redis_stop_event=redis_stop_event,
                    redis_task=redis_task,
                    processed_ids=processed_ids,
                )

            else:
                await websocket.send_json(
                    ErrorResponse(
                        message=f"Unknown message type: {msg_type}",
                        code="UNKNOWN_TYPE"
                    ).model_dump()
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: connection_id={connection_id}")

    except Exception as e:
        logger.error(f"WebSocket error: connection_id={connection_id}, error={e}")
        try:
            await websocket.send_json(
                ErrorResponse(
                    message=str(e),
                    code="INTERNAL_ERROR"
                ).model_dump()
            )
        except:
            pass

    finally:
        # 停止 Redis 订阅
        redis_stop_event.set()
        if redis_task:
            try:
                await asyncio.wait_for(redis_task, timeout=5.0)
            except asyncio.TimeoutError:
                redis_task.cancel()

        # 清理资源
        user_id_result = await manager.disconnect(connection_id)

        # 关闭 iflow_client 连接（WebSocket 断开时）
        if iflow_client is not None:
            try:
                await iflow_client.disconnect()
                logger.info(f"Closed iFlow client when WebSocket disconnected")
            except Exception as e:
                logger.warning(f"Error closing iFlow client: {e}")

        # 关闭消息缓冲
        try:
            await message_buffer.close()
        except:
            pass

        # 关闭数据库会话
        try:
            await db_gen.aclose()
        except:
            pass


# ==================== 辅助函数 ====================

async def authenticate_connection(
    websocket: WebSocket,
    manager: WebSocketManager,
    connection_id: str,
    expected_user_id: int,
    token: str,
) -> bool:
    """
    认证 WebSocket 连接

    Args:
        websocket: WebSocket 连接
        manager: WebSocket 管理器
        connection_id: 连接 ID
        expected_user_id: 预期的用户 ID
        token: JWT Token

    Returns:
        bool: 是否认证成功
    """
    # 解码 token
    payload = decode_access_token(token)

    if payload is None:
        await websocket.send_json(
            AuthFailedResponse(message="Invalid token").model_dump()
        )
        return False

    # 验证用户 ID
    token_user_id = payload.get("sub")
    if token_user_id != expected_user_id:
        await websocket.send_json(
            AuthFailedResponse(message="User ID mismatch").model_dump()
        )
        return False

    # 标记为已认证
    await manager.authenticate(connection_id)

    # 发送认证成功响应
    await websocket.send_json(
        AuthSuccessResponse(
            user_id=expected_user_id,
            username=payload.get("username", "")
        ).model_dump()
    )

    logger.info(f"WebSocket authenticated: user_id={expected_user_id}, connection_id={connection_id}")
    return True


async def handle_chat_message_eventbus(
    websocket: WebSocket,
    manager: WebSocketManager,
    connection_id: str,
    user_id: int,
    content: str,
    db: AsyncSession,
    iflow_client: Optional[IFlowClientService],
    input_handler: WebSocketInputHandler,
    message_buffer: MessageBuffer,
    current_conversation_id: Optional[int] = None,
    working_directory: Optional[str] = None,
    redis_stop_event: Optional[asyncio.Event] = None,
    redis_task: Optional[asyncio.Task] = None,
    processed_ids: Optional[Set[str]] = None,
) -> Tuple[Optional[int], Optional[IFlowClientService]]:
    """
    处理聊天消息（使用 EventBus）

    通过 EventBus 发射 user_message 信号，由 IFlowProcessor 处理 AI 对话，
    通过 Redis 订阅接收响应并推送给 WebSocket。

    Args:
        websocket: WebSocket 连接
        manager: WebSocket 管理器
        connection_id: 连接 ID
        user_id: 用户 ID
        content: 消息内容
        db: 数据库会话
        iflow_client: iFlow 客户端（可选，保持兼容性）
        input_handler: WebSocket 输入处理器
        message_buffer: 消息缓冲服务
        current_conversation_id: 当前会话 ID（可选）
        working_directory: 工作目录（可选，创建新会话时使用）
        redis_stop_event: Redis 订阅停止信号
        redis_task: Redis 订阅任务
        processed_ids: 已处理的消息 ID 集合

    Returns:
        Tuple[Optional[int], Optional[IFlowClientService]]: (更新后的会话 ID, 更新后的 iFlow 客户端)
    """
    logger.debug(f"Handling chat message (EventBus): user_id={user_id}, content={content[:50]}...")

    # 获取或创建会话
    conversation_service = ConversationService(db)
    conversation = None

    if current_conversation_id:
        # 验证会话存在且属于该用户
        conversation = await conversation_service.get_conversation(current_conversation_id, user_id)
        if not conversation:
            logger.warning(f"Conversation {current_conversation_id} not found for user {user_id}")
            current_conversation_id = None

    if not current_conversation_id:
        # 创建新会话，使用指定的或默认的工作目录
        effective_working_directory = working_directory or "/root/.iflow-bot/workspace"

        # 断开旧的 iflow_client 连接
        if iflow_client is not None:
            try:
                await iflow_client.disconnect()
                logger.info(f"Disconnected old iFlow client when creating new conversation")
            except Exception as e:
                logger.warning(f"Error disconnecting old iFlow client: {e}")
            iflow_client = None

        conversation = await conversation_service.create_conversation(
            user_id=user_id,
            working_directory=effective_working_directory,
        )
        current_conversation_id = conversation.id
        logger.info(f"Created new conversation {current_conversation_id} for user {user_id} with working_directory={effective_working_directory}")

    # 保存用户消息到数据库
    user_msg = ChatHistory(
        user_id=user_id,
        conversation_id=current_conversation_id,
        role="user",
        content=content,
    )
    db.add(user_msg)
    await db.commit()

    # 如果会话标题是"新会话"，自动更新为用户消息的前20字符
    if conversation and conversation.title == "新会话":
        new_title = content[:20]
        if len(content) > 20:
            new_title += "..."
        conversation.title = new_title
        await db.commit()
        logger.info(f"Auto updated conversation {current_conversation_id} title to: {new_title}")

    # 获取工作目录
    cwd = conversation.working_directory if conversation else working_directory or "/root/.iflow-bot/workspace"

    # 使用 WebSocketInputHandler 发射 user_message 信号
    input_handler.handle(
        user_id=user_id,
        content=content,
        conversation_id=current_conversation_id,
        working_directory=cwd,
    )

    # 启动 Redis 订阅任务（如果尚未启动）
    if redis_task is None and redis_stop_event is not None and processed_ids is not None:
        redis_task = asyncio.create_task(
            subscribe_redis_messages(
                websocket=websocket,
                user_id=user_id,
                message_buffer=message_buffer,
                stop_event=redis_stop_event,
                processed_ids=processed_ids,
                conversation_id=current_conversation_id,
            )
        )

    # 等待响应完成（通过监听 Redis Stream）
    # 这里使用一个简单的轮询机制，等待收到 complete 消息
    complete_received = False
    timeout = 60.0  # 60秒超时
    start_time = asyncio.get_event_loop().time()

    while not complete_received:
        # 检查超时
        if asyncio.get_event_loop().time() - start_time > timeout:
            logger.warning(f"Timeout waiting for AI response: user_id={user_id}")
            await websocket.send_json(
                ErrorResponse(
                    message="Response timeout",
                    code="RESPONSE_TIMEOUT"
                ).model_dump()
            )
            break

        # 从 Redis 获取消息
        pending = await message_buffer.get_pending(user_id, count=10)

        if pending:
            for stream_name, entries in pending:
                for entry_id, fields in entries:
                    # 跳过已处理的消息
                    if entry_id in (processed_ids or set()):
                        continue

                    # 标记为已处理
                    if processed_ids is not None:
                        processed_ids.add(entry_id)

                    # 解析消息
                    try:
                        data = json.loads(fields.get('data', '{}'))
                    except json.JSONDecodeError:
                        continue

                    # 过滤会话 ID
                    msg_conversation_id = data.get('conversation_id')
                    if msg_conversation_id is not None and msg_conversation_id != current_conversation_id:
                        continue

                    msg_type = data.get('type')

                    if msg_type == 'stream':
                        # 流式响应
                        await websocket.send_json(
                            AssistantMessageResponse(
                                content=data.get('content', ''),
                                is_delta=data.get('is_delta', True),
                                is_finished=False,
                            ).model_dump()
                        )

                    elif msg_type == 'complete':
                        # 完成响应
                        complete_received = True
                        await websocket.send_json(
                            AssistantMessageResponse(
                                content='',
                                is_delta=False,
                                is_finished=True,
                            ).model_dump()
                        )

                        # 保存助手响应到数据库
                        response_text = data.get('content', '')
                        if response_text:
                            # 检查定时任务意图
                            task_intent = extract_task_intent(response_text)
                            if task_intent:
                                cleaned_response = remove_task_json_from_response(response_text)
                                task_description = task_intent.get("description", content)
                                await try_create_task_from_intent(
                                    websocket=websocket,
                                    user_id=user_id,
                                    description=task_description,
                                )
                                response_text = cleaned_response

                            assistant_msg = ChatHistory(
                                user_id=user_id,
                                conversation_id=current_conversation_id,
                                role="assistant",
                                content=response_text,
                            )
                            db.add(assistant_msg)
                            await db.commit()

                        # 消费已处理的消息
                        await message_buffer.consume(user_id, count=len(processed_ids or set()))

        # 短暂等待
        await asyncio.sleep(0.05)

    # 更新会话的活动时间
    await conversation_service.touch_conversation(current_conversation_id, user_id)

    return current_conversation_id, iflow_client


async def handle_chat_message(
    websocket: WebSocket,
    manager: WebSocketManager,
    connection_id: str,
    user_id: int,
    content: str,
    db: AsyncSession,
    iflow_client: Optional[IFlowClientService],
    current_conversation_id: Optional[int] = None,
    working_directory: Optional[str] = None,
) -> Tuple[Optional[int], Optional[IFlowClientService]]:
    """
    处理聊天消息（直接调用 iFlow，保持向后兼容）

    注意：此方法已弃用，建议使用 handle_chat_message_eventbus

    Args:
        websocket: WebSocket 连接
        manager: WebSocket 管理器
        connection_id: 连接 ID
        user_id: 用户 ID
        content: 消息内容
        db: 数据库会话
        iflow_client: iFlow 客户端（可选）
        current_conversation_id: 当前会话 ID（可选）
        working_directory: 工作目录（可选，创建新会话时使用）

    Returns:
        Tuple[Optional[int], Optional[IFlowClientService]]: (更新后的会话 ID, 更新后的 iFlow 客户端)
    """
    logger.debug(f"Handling chat message: user_id={user_id}, content={content[:50]}...")

    # 获取或创建会话
    conversation_service = ConversationService(db)
    conversation = None

    if current_conversation_id:
        # 验证会话存在且属于该用户
        conversation = await conversation_service.get_conversation(current_conversation_id, user_id)
        if not conversation:
            logger.warning(f"Conversation {current_conversation_id} not found for user {user_id}")
            current_conversation_id = None

    if not current_conversation_id:
        # 创建新会话，使用指定的或默认的工作目录
        effective_working_directory = working_directory or "/root/.iflow-bot/workspace"

        # 断开旧的 iflow_client 连接
        if iflow_client is not None:
            try:
                await iflow_client.disconnect()
                logger.info(f"Disconnected old iFlow client when creating new conversation")
            except Exception as e:
                logger.warning(f"Error disconnecting old iFlow client: {e}")
            iflow_client = None

        conversation = await conversation_service.create_conversation(
            user_id=user_id,
            working_directory=effective_working_directory,
        )
        current_conversation_id = conversation.id
        logger.info(f"Created new conversation {current_conversation_id} for user {user_id} with working_directory={effective_working_directory}")

    # 保存用户消息到数据库
    user_msg = ChatHistory(
        user_id=user_id,
        conversation_id=current_conversation_id,
        role="user",
        content=content,
    )
    db.add(user_msg)
    await db.commit()

    # 如果会话标题是"新会话"，自动更新为用户消息的前20字符
    if conversation and conversation.title == "新会话":
        new_title = content[:20]
        if len(content) > 20:
            new_title += "..."
        conversation.title = new_title
        await db.commit()
        logger.info(f"Auto updated conversation {current_conversation_id} title to: {new_title}")

    # 获取用户的 session 信息
    user_session = manager.get_or_create_user_session(user_id)

    # 创建或重用 iFlow 客户端
    if iflow_client is None:
        # 使用会话的工作目录创建客户端
        cwd = conversation.working_directory if conversation else working_directory or "/root/.iflow-bot/workspace"
        iflow_client = IFlowClientService(
            cwd=cwd,
            session_id=user_session.session_id,
        )
        try:
            await iflow_client.connect()
            # 更新用户的 session_id
            if iflow_client.session_id:
                manager.update_user_session(user_id, session_id=iflow_client.session_id, iflow_client=iflow_client)
        except Exception as e:
            logger.error(f"Failed to connect to iFlow: {e}")
            await websocket.send_json(
                ErrorResponse(
                    message="Failed to connect to AI service",
                    code="IFLOW_ERROR"
                ).model_dump()
            )
            return current_conversation_id, iflow_client

    # 发送消息到 iFlow 并处理响应
    # 启用定时任务意图检测
    full_response = []

    try:
        async for msg in iflow_client.query_stream(content, enable_task_detection=True):
            if msg.type == IFlowMessageType.TEXT:
                # 文本消息
                if msg.content:
                    full_response.append(msg.content)

                # 始终发送消息，包括空内容的完成消息
                await websocket.send_json(
                    AssistantMessageResponse(
                        content=msg.content,
                        is_delta=msg.is_delta,
                        is_finished=msg.is_finished,
                    ).model_dump()
                )

            elif msg.type == IFlowMessageType.TOOL_CALL:
                # 工具调用
                await websocket.send_json(
                    ToolCallResponse(
                        tool_id=msg.tool_id,
                        tool_name=msg.tool_name or "",
                        arguments=msg.tool_arguments or {},
                        status=msg.tool_status or "in_progress",
                        result=msg.tool_result,
                        error=msg.tool_error,
                    ).model_dump()
                )

            elif msg.type == IFlowMessageType.ERROR:
                # 错误
                await websocket.send_json(
                    ErrorResponse(
                        message=msg.content,
                        code="IFLOW_ERROR"
                    ).model_dump()
                )

            elif msg.type == IFlowMessageType.TASK_FINISH:
                # 任务完成 - 发送完成标记给前端
                await websocket.send_json(
                    AssistantMessageResponse(
                        content="",
                        is_delta=False,
                        is_finished=True,
                    ).model_dump()
                )

    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        await websocket.send_json(
            ErrorResponse(
                message=str(e),
                code="PROCESSING_ERROR"
            ).model_dump()
        )
        return current_conversation_id, iflow_client

    # 处理完整的 AI 响应
    response_text = "".join(full_response)

    # 检查是否有定时任务意图
    task_intent = extract_task_intent(response_text)
    if task_intent:
        # 从响应中移除 JSON 块
        cleaned_response = remove_task_json_from_response(response_text)

        # 尝试创建定时任务
        task_description = task_intent.get("description", content)
        task_created = await try_create_task_from_intent(
            websocket=websocket,
            user_id=user_id,
            description=task_description,
        )

        # 更新保存的响应内容（移除 JSON 块）
        response_text = cleaned_response

    # 保存助手响应到数据库
    if response_text:
        assistant_msg = ChatHistory(
            user_id=user_id,
            conversation_id=current_conversation_id,
            role="assistant",
            content=response_text,
        )
        db.add(assistant_msg)
        await db.commit()

    # 更新会话的 iFlow session_id
    if iflow_client and iflow_client.session_id:
        await conversation_service.update_conversation_iflow_session(
            conversation_id=current_conversation_id,
            user_id=user_id,
            iflow_session_id=iflow_client.session_id,
        )

    # 更新会话的活动时间
    await conversation_service.touch_conversation(current_conversation_id, user_id)

    return current_conversation_id, iflow_client


async def handle_switch_conversation(
    websocket: WebSocket,
    manager: WebSocketManager,
    user_id: int,
    conversation_id: int,
    db: AsyncSession,
    current_conversation_id: Optional[int],
    iflow_client: Optional[IFlowClientService],
) -> Tuple[Optional[int], Optional[IFlowClientService]]:
    """
    处理切换会话

    切换会话时会断开旧的 iflow_client 连接，并使用目标会话的 working_directory 创建新连接。
    这确保每个会话使用正确的工作目录。

    Args:
        websocket: WebSocket 连接
        manager: WebSocket 管理器
        user_id: 用户 ID
        conversation_id: 目标会话 ID
        db: 数据库会话
        current_conversation_id: 当前会话 ID
        iflow_client: iFlow 客户端

    Returns:
        Tuple[Optional[int], Optional[IFlowClientService]]: (切换后的会话 ID, 更新后的 iFlow 客户端)
    """
    logger.info(f"Switching conversation: user_id={user_id}, from={current_conversation_id}, to={conversation_id}")

    conversation_service = ConversationService(db)

    # 获取目标会话
    conversation = await conversation_service.get_conversation(conversation_id, user_id)
    if not conversation:
        await websocket.send_json(
            ErrorResponse(
                message="Conversation not found or access denied",
                code="CONVERSATION_NOT_FOUND"
            ).model_dump()
        )
        return current_conversation_id, iflow_client

    # 获取会话的工作目录（如果为空则使用默认值）
    working_directory = conversation.working_directory or "/root/.iflow-bot/workspace"

    # 断开旧的 iflow_client 连接
    if iflow_client is not None:
        try:
            await iflow_client.disconnect()
            logger.info(f"Disconnected old iFlow client when switching conversation")
        except Exception as e:
            logger.warning(f"Error disconnecting old iFlow client: {e}")
        iflow_client = None

    # 使用会话的 working_directory 创建新的 iFlow 客户端
    session_id = conversation.iflow_session_id if conversation.iflow_session_id else None
    iflow_client = IFlowClientService(
        cwd=working_directory,
        session_id=session_id,
    )
    try:
        await iflow_client.connect()
        logger.info(f"Created new iFlow client with cwd={working_directory}, session_id={session_id}")

        # 如果会话没有 iflow_session_id，保存新的 session_id
        if not conversation.iflow_session_id and iflow_client.session_id:
            await conversation_service.update_conversation_iflow_session(
                conversation_id=conversation_id,
                user_id=user_id,
                iflow_session_id=iflow_client.session_id,
            )
    except Exception as e:
        logger.error(f"Failed to create iFlow connection: {e}")
        await websocket.send_json(
            ErrorResponse(
                message="Failed to connect to AI service",
                code="IFLOW_ERROR"
            ).model_dump()
        )
        return current_conversation_id, iflow_client

    # 发送切换成功响应
    await websocket.send_json(
        ConversationSwitchedResponse(
            conversation_id=conversation.id,
            title=conversation.title,
            iflow_session_id=conversation.iflow_session_id,
        ).model_dump()
    )

    logger.info(f"Conversation switched: user_id={user_id}, conversation_id={conversation_id}, working_directory={working_directory}")

    return conversation_id, iflow_client


async def try_create_task_from_intent(
    websocket: WebSocket,
    user_id: int,
    description: str,
) -> bool:
    """
    尝试从意图创建定时任务

    Args:
        websocket: WebSocket 连接
        user_id: 用户 ID
        description: 任务描述

    Returns:
        bool: 是否创建成功
    """
    from backend.services.notification_store import get_notification_store

    logger.info(f"Trying to create task from intent: user_id={user_id}, description={description}")

    notification_store = get_notification_store()

    try:
        # 解析自然语言
        parser = get_task_parser()
        parsed_task = await parser.parse(description)

        if not parsed_task.success:
            logger.warning(f"Failed to parse task: {parsed_task.error}")
            # 保存并发送错误通知
            notification = notification_store.add_notification(
                user_id=user_id,
                task_id=None,
                content=f"定时任务创建失败：{parsed_task.error}",
            )
            await websocket.send_json(
                NotificationResponse(notification=notification).model_dump()
            )
            return False

        # 验证 Cron 表达式
        if not parser.validate_cron(parsed_task.cron_expression):
            logger.warning(f"Invalid cron expression: {parsed_task.cron_expression}")
            notification = notification_store.add_notification(
                user_id=user_id,
                task_id=None,
                content="定时任务创建失败：生成的时间表达式无效",
            )
            await websocket.send_json(
                NotificationResponse(notification=notification).model_dump()
            )
            return False

        # 创建任务
        scheduler = get_scheduler()
        task = scheduler.add_task(
            user_id=user_id,
            content=parsed_task.content,
            cron=parsed_task.cron_expression,
            natural_language=description,
            enabled=True
        )

        logger.info(f"Task created successfully: task_id={task.id}, cron={task.cron}")

        # 保存并发送任务创建成功通知
        notification = notification_store.add_notification(
            user_id=user_id,
            task_id=task.id,
            content=f"✅ 定时任务创建成功！\n任务：{parsed_task.content}\n时间：{description}\nCron：{task.cron}",
        )
        await websocket.send_json(
            NotificationResponse(notification=notification).model_dump()
        )

        return True

    except Exception as e:
        logger.error(f"Error creating task: {e}")
        notification = notification_store.add_notification(
            user_id=user_id,
            task_id=None,
            content=f"定时任务创建失败：{str(e)}",
        )
        await websocket.send_json(
            NotificationResponse(notification=notification).model_dump()
        )
        return False