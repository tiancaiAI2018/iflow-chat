"""
会话服务层
提供会话的 CRUD 操作、AI 标题生成等功能
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.user import User, Conversation, ChatHistory
from backend.models.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
    ConversationDetailResponse,
    ChatMessageResponse,
)
from backend.services.iflow_client import IFlowClientService, MessageType

logger = logging.getLogger(__name__)


# AI 生成标题的系统提示词
TITLE_GENERATION_PROMPT = """请为以下对话生成一个简短的标题（不超过20个字）。
只返回标题本身，不要加引号或其他符号。

用户消息：
{message}

标题："""


class ConversationService:
    """
    会话服务类
    提供会话的创建、查询、更新、删除等功能
    """
    
    def __init__(self, db: AsyncSession):
        """
        初始化会话服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def create_conversation(
        self,
        user_id: int,
        title: Optional[str] = None,
        first_message: Optional[str] = None,
        working_directory: Optional[str] = None,
    ) -> Conversation:
        """
        创建新会话
        
        Args:
            user_id: 用户 ID
            title: 会话标题（可选）
            first_message: 首条消息（用于生成简单标题，不调用 AI）
            working_directory: 工作目录（可选，默认为 /root/.iflow-bot/workspace）
        
        Returns:
            Conversation: 创建的会话对象
        """
        # 生成标题：优先使用传入的标题，其次用首条消息截取，最后使用默认值
        if title:
            pass  # 使用传入的标题
        elif first_message:
            # 截取消息前 20 字符作为标题，不调用 AI
            title = first_message[:20]
            if len(first_message) > 20:
                title += "..."
        else:
            title = "新会话"
        
        # 创建会话
        conversation = Conversation(
            user_id=user_id,
            title=title,
            working_directory=working_directory or "/root/.iflow-bot/workspace",
        )
        
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        
        logger.info(f"Created conversation {conversation.id} for user {user_id}: {title}, working_directory={conversation.working_directory}")
        return conversation
    
    async def get_user_conversations(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Conversation], int]:
        """
        获取用户的会话列表（按更新时间倒序）
        
        Args:
            user_id: 用户 ID
            limit: 返回数量限制
            offset: 偏移量
        
        Returns:
            Tuple[List[Conversation], int]: (会话列表, 总数)
        """
        # 查询总数
        count_query = select(func.count()).select_from(Conversation).where(
            Conversation.user_id == user_id
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # 查询会话列表（按更新时间倒序）
        query = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.db.execute(query)
        conversations = list(result.scalars().all())
        
        return conversations, total
    
    async def get_conversation(
        self,
        conversation_id: int,
        user_id: int,
    ) -> Optional[Conversation]:
        """
        获取单个会话（验证用户权限）
        
        Args:
            conversation_id: 会话 ID
            user_id: 用户 ID
        
        Returns:
            Optional[Conversation]: 会话对象，不存在或无权限则返回 None
        """
        query = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_conversation_with_messages(
        self,
        conversation_id: int,
        user_id: int,
        message_limit: int = 100,
    ) -> Optional[Tuple[Conversation, List[ChatHistory]]]:
        """
        获取会话详情及其消息历史
        
        Args:
            conversation_id: 会话 ID
            user_id: 用户 ID
            message_limit: 消息数量限制
        
        Returns:
            Optional[Tuple[Conversation, List[ChatHistory]]]: (会话, 消息列表)，不存在则返回 None
        """
        # 获取会话
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            return None
        
        # 获取消息历史（按时间正序）
        messages_query = (
            select(ChatHistory)
            .where(ChatHistory.conversation_id == conversation_id)
            .order_by(ChatHistory.created_at.asc())
            .limit(message_limit)
        )
        
        result = await self.db.execute(messages_query)
        messages = list(result.scalars().all())
        
        return conversation, messages
    
    async def delete_conversation(
        self,
        conversation_id: int,
        user_id: int,
    ) -> bool:
        """
        删除会话及其消息
        
        Args:
            conversation_id: 会话 ID
            user_id: 用户 ID
        
        Returns:
            bool: 是否删除成功
        """
        # 先验证会话存在且属于该用户
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            return False
        
        # 删除会话（级联删除消息）
        await self.db.delete(conversation)
        await self.db.commit()
        
        logger.info(f"Deleted conversation {conversation_id} for user {user_id}")
        return True
    
    async def update_conversation_title(
        self,
        conversation_id: int,
        user_id: int,
        new_title: str,
    ) -> Optional[Conversation]:
        """
        更新会话标题
        
        Args:
            conversation_id: 会话 ID
            user_id: 用户 ID
            new_title: 新标题
        
        Returns:
            Optional[Conversation]: 更新后的会话，不存在则返回 None
        """
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            return None
        
        conversation.title = new_title
        conversation.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(conversation)
        
        logger.info(f"Updated conversation {conversation_id} title to: {new_title}")
        return conversation
    
    async def update_conversation_iflow_session(
        self,
        conversation_id: int,
        user_id: int,
        iflow_session_id: str,
    ) -> Optional[Conversation]:
        """
        更新会话的 iFlow session ID
        
        Args:
            conversation_id: 会话 ID
            user_id: 用户 ID
            iflow_session_id: iFlow 会话 ID
        
        Returns:
            Optional[Conversation]: 更新后的会话，不存在则返回 None
        """
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            return None
        
        conversation.iflow_session_id = iflow_session_id
        conversation.updated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(conversation)
        
        logger.info(f"Updated conversation {conversation_id} iFlow session to: {iflow_session_id}")
        return conversation
    
    async def touch_conversation(
        self,
        conversation_id: int,
        user_id: int,
    ) -> bool:
        """
        更新会话的 updated_at 时间戳（用于标记会话活动）
        
        Args:
            conversation_id: 会话 ID
            user_id: 用户 ID
        
        Returns:
            bool: 是否更新成功
        """
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            return False
        
        conversation.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        
        return True
    
    async def generate_title_from_message(self, message: str) -> str:
        """
        使用 AI 从首条消息生成会话标题
        
        Args:
            message: 首条消息内容
        
        Returns:
            str: 生成的标题
        """
        if not message or not message.strip():
            return "新会话"
        
        # 截取消息前 200 字符（避免太长）
        truncated_message = message[:200] if len(message) > 200 else message
        
        try:
            # 使用 iFlow 客户端生成标题
            client = IFlowClientService()
            prompt = TITLE_GENERATION_PROMPT.format(message=truncated_message)
            
            # 同步方式获取标题
            async with client:
                title = await client.query(prompt)
            
            # 清理标题
            title = title.strip()
            
            # 移除可能的引号
            if title.startswith('"') and title.endswith('"'):
                title = title[1:-1]
            if title.startswith("'") and title.endswith("'"):
                title = title[1:-1]
            
            # 限制标题长度
            if len(title) > 50:
                title = title[:47] + "..."
            
            # 如果生成失败或太短，使用默认标题
            if not title or len(title) < 2:
                title = "新会话"
            
            logger.info(f"Generated title from message: {title}")
            return title
            
        except Exception as e:
            logger.warning(f"Failed to generate title from message: {e}")
            # 回退到使用消息前 20 字符
            fallback = truncated_message[:20]
            if len(truncated_message) > 20:
                fallback += "..."
            return fallback if fallback.strip() else "新会话"
    
    async def get_or_create_conversation(
        self,
        user_id: int,
        conversation_id: Optional[int] = None,
        working_directory: Optional[str] = None,
    ) -> Conversation:
        """
        获取或创建会话
        如果提供了 conversation_id 且存在，返回该会话
        否则创建新会话
        
        Args:
            user_id: 用户 ID
            conversation_id: 会话 ID（可选）
            working_directory: 工作目录（可选，创建新会话时使用）
        
        Returns:
            Conversation: 会话对象
        """
        if conversation_id:
            conversation = await self.get_conversation(conversation_id, user_id)
            if conversation:
                return conversation
        
        # 创建新会话
        return await self.create_conversation(user_id, working_directory=working_directory)


# 辅助函数

def conversation_to_response(conversation: Conversation) -> ConversationResponse:
    """
    将 Conversation ORM 对象转换为响应模型
    
    Args:
        conversation: 会话 ORM 对象
    
    Returns:
        ConversationResponse: 响应模型
    """
    return ConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        iflow_session_id=conversation.iflow_session_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def chat_history_to_response(message: ChatHistory) -> ChatMessageResponse:
    """
    将 ChatHistory ORM 对象转换为响应模型
    
    Args:
        message: 聊天历史 ORM 对象
    
    Returns:
        ChatMessageResponse: 响应模型
    """
    return ChatMessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )
