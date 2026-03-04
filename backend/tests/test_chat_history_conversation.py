"""
测试 ChatHistory 与 Conversation 的外键关联
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from backend.database import Base
from backend.models.user import User, Conversation, ChatHistory


# 使用内存数据库进行测试
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_maker = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="function")
async def db_session():
    """创建测试数据库会话"""
    # 创建所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with test_session_maker() as session:
        yield session
    
    # 清理：删除所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class TestChatHistoryConversationRelation:
    """ChatHistory 与 Conversation 关联测试类"""

    @pytest.mark.asyncio
    async def test_chat_history_with_conversation(self, db_session: AsyncSession):
        """测试 ChatHistory 关联 conversation_id"""
        # 创建用户
        user = User(
            username="chatuser",
            email="chatuser@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 创建会话
        conversation = Conversation(
            user_id=user.id,
            title="测试会话"
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        # 创建聊天历史并关联会话
        chat = ChatHistory(
            user_id=user.id,
            conversation_id=conversation.id,
            role="user",
            content="你好"
        )
        db_session.add(chat)
        await db_session.commit()
        await db_session.refresh(chat)

        assert chat.id is not None
        assert chat.conversation_id == conversation.id
        assert chat.role == "user"
        assert chat.content == "你好"

    @pytest.mark.asyncio
    async def test_chat_history_nullable_conversation_id(self, db_session: AsyncSession):
        """测试 conversation_id 可为空（兼容现有数据）"""
        user = User(
            username="nullconv",
            email="nullconv@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 创建不关联会话的聊天历史
        chat = ChatHistory(
            user_id=user.id,
            role="user",
            content="无会话消息"
        )
        db_session.add(chat)
        await db_session.commit()
        await db_session.refresh(chat)

        assert chat.conversation_id is None

    @pytest.mark.asyncio
    async def test_conversation_messages_relationship(self, db_session: AsyncSession):
        """测试 Conversation 与 ChatHistory 的一对多关系"""
        user = User(
            username="msgrelation",
            email="msgrelation@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 创建会话
        conversation = Conversation(
            user_id=user.id,
            title="消息关系测试"
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        # 创建多条聊天历史
        chat1 = ChatHistory(
            user_id=user.id,
            conversation_id=conversation.id,
            role="user",
            content="问题1"
        )
        chat2 = ChatHistory(
            user_id=user.id,
            conversation_id=conversation.id,
            role="assistant",
            content="回答1"
        )
        chat3 = ChatHistory(
            user_id=user.id,
            conversation_id=conversation.id,
            role="user",
            content="问题2"
        )
        db_session.add_all([chat1, chat2, chat3])
        await db_session.commit()

        # 查询会话并加载消息关系
        result = await db_session.execute(
            select(Conversation)
            .where(Conversation.id == conversation.id)
            .options(selectinload(Conversation.messages))
        )
        conv_with_messages = result.scalar_one()

        assert len(conv_with_messages.messages) == 3
        contents = [m.content for m in conv_with_messages.messages]
        assert "问题1" in contents
        assert "回答1" in contents
        assert "问题2" in contents

    @pytest.mark.asyncio
    async def test_chat_history_conversation_back_populates(self, db_session: AsyncSession):
        """测试 ChatHistory.conversation 反向关系"""
        user = User(
            username="backpop",
            email="backpop@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        conversation = Conversation(
            user_id=user.id,
            title="反向关系测试"
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        chat = ChatHistory(
            user_id=user.id,
            conversation_id=conversation.id,
            role="user",
            content="测试反向关系"
        )
        db_session.add(chat)
        await db_session.commit()
        await db_session.refresh(chat)

        # 通过 chat 访问 conversation
        assert chat.conversation is not None
        assert chat.conversation.id == conversation.id
        assert chat.conversation.title == "反向关系测试"

    @pytest.mark.asyncio
    async def test_conversation_cascade_delete_messages(self, db_session: AsyncSession):
        """测试删除会话时级联删除聊天历史"""
        user = User(
            username="cascademsg",
            email="cascademsg@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 创建会话
        conversation = Conversation(
            user_id=user.id,
            title="将被删除的会话"
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)
        conv_id = conversation.id

        # 创建聊天历史
        chat = ChatHistory(
            user_id=user.id,
            conversation_id=conv_id,
            role="user",
            content="将被级联删除"
        )
        db_session.add(chat)
        await db_session.commit()
        await db_session.refresh(chat)
        chat_id = chat.id

        # 删除会话
        await db_session.delete(conversation)
        await db_session.commit()

        # 检查聊天历史是否被级联删除
        result = await db_session.execute(
            select(ChatHistory).where(ChatHistory.id == chat_id)
        )
        deleted_chat = result.scalar_one_or_none()
        assert deleted_chat is None

    @pytest.mark.asyncio
    async def test_query_chat_history_by_conversation(self, db_session: AsyncSession):
        """测试按会话查询聊天历史"""
        user = User(
            username="queryconv",
            email="queryconv@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 创建两个会话
        conv1 = Conversation(user_id=user.id, title="会话1")
        conv2 = Conversation(user_id=user.id, title="会话2")
        db_session.add_all([conv1, conv2])
        await db_session.commit()
        await db_session.refresh(conv1)
        await db_session.refresh(conv2)

        # 为每个会话创建聊天历史
        chat1 = ChatHistory(
            user_id=user.id, conversation_id=conv1.id, role="user", content="会话1消息"
        )
        chat2 = ChatHistory(
            user_id=user.id, conversation_id=conv1.id, role="assistant", content="会话1回复"
        )
        chat3 = ChatHistory(
            user_id=user.id, conversation_id=conv2.id, role="user", content="会话2消息"
        )
        db_session.add_all([chat1, chat2, chat3])
        await db_session.commit()

        # 查询 conv1 的聊天历史
        result = await db_session.execute(
            select(ChatHistory)
            .where(ChatHistory.conversation_id == conv1.id)
            .order_by(ChatHistory.created_at)
        )
        conv1_chats = result.scalars().all()

        assert len(conv1_chats) == 2
        for chat in conv1_chats:
            assert chat.conversation_id == conv1.id

    @pytest.mark.asyncio
    async def test_chat_history_repr_with_conversation(self, db_session: AsyncSession):
        """测试 ChatHistory 的字符串表示包含 conversation_id"""
        user = User(
            username="reprconv",
            email="reprconv@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        conversation = Conversation(
            user_id=user.id,
            title="repr测试会话"
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        chat = ChatHistory(
            user_id=user.id,
            conversation_id=conversation.id,
            role="user",
            content="repr测试"
        )
        db_session.add(chat)
        await db_session.commit()
        await db_session.refresh(chat)

        repr_str = repr(chat)
        assert "ChatHistory" in repr_str
        assert str(chat.id) in repr_str
        assert str(chat.user_id) in repr_str
        assert str(chat.conversation_id) in repr_str
        assert "user" in repr_str

    @pytest.mark.asyncio
    async def test_multiple_conversations_isolation(self, db_session: AsyncSession):
        """测试多个会话之间的消息隔离"""
        user = User(
            username="isolated",
            email="isolated@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 创建两个会话
        conv1 = Conversation(user_id=user.id, title="会话A")
        conv2 = Conversation(user_id=user.id, title="会话B")
        db_session.add_all([conv1, conv2])
        await db_session.commit()
        await db_session.refresh(conv1)
        await db_session.refresh(conv2)

        # 为每个会话添加消息
        chats = [
            ChatHistory(user_id=user.id, conversation_id=conv1.id, role="user", content="A1"),
            ChatHistory(user_id=user.id, conversation_id=conv1.id, role="assistant", content="A2"),
            ChatHistory(user_id=user.id, conversation_id=conv2.id, role="user", content="B1"),
            ChatHistory(user_id=user.id, conversation_id=conv2.id, role="assistant", content="B2"),
        ]
        db_session.add_all(chats)
        await db_session.commit()

        # 验证会话A只有A1和A2
        result_a = await db_session.execute(
            select(ChatHistory)
            .where(ChatHistory.conversation_id == conv1.id)
            .options(selectinload(ChatHistory.conversation))
        )
        conv_a_messages = result_a.scalars().all()
        assert len(conv_a_messages) == 2
        assert all(m.conversation.title == "会话A" for m in conv_a_messages)

        # 验证会话B只有B1和B2
        result_b = await db_session.execute(
            select(ChatHistory)
            .where(ChatHistory.conversation_id == conv2.id)
            .options(selectinload(ChatHistory.conversation))
        )
        conv_b_messages = result_b.scalars().all()
        assert len(conv_b_messages) == 2
        assert all(m.conversation.title == "会话B" for m in conv_b_messages)
