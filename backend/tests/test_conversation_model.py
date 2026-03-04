"""
测试 Conversation ORM 模型
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from backend.database import Base
from backend.models.user import User, Conversation


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


class TestConversationModel:
    """Conversation 模型测试类"""

    @pytest.mark.asyncio
    async def test_create_conversation(self, db_session: AsyncSession):
        """测试创建会话"""
        # 先创建用户
        user = User(
            username="convuser",
            email="conv@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 创建会话
        conversation = Conversation(
            user_id=user.id,
            title="测试会话",
            iflow_session_id="session-123"
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        assert conversation.id is not None
        assert conversation.user_id == user.id
        assert conversation.title == "测试会话"
        assert conversation.iflow_session_id == "session-123"
        assert conversation.created_at is not None
        assert conversation.updated_at is not None

    @pytest.mark.asyncio
    async def test_conversation_default_title(self, db_session: AsyncSession):
        """测试会话默认标题"""
        user = User(
            username="defaulttitle",
            email="defaulttitle@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 不指定标题创建会话
        conversation = Conversation(user_id=user.id)
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        assert conversation.title == "新会话"

    @pytest.mark.asyncio
    async def test_conversation_nullable_iflow_session_id(self, db_session: AsyncSession):
        """测试 iflow_session_id 可为空"""
        user = User(
            username="nullsession",
            email="nullsession@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 不指定 iflow_session_id
        conversation = Conversation(
            user_id=user.id,
            title="无 session"
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        assert conversation.iflow_session_id is None

    @pytest.mark.asyncio
    async def test_user_conversation_relationship(self, db_session: AsyncSession):
        """测试用户与会话的一对多关系"""
        user = User(
            username="relationuser",
            email="relationuser@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 创建多个会话
        conv1 = Conversation(user_id=user.id, title="会话1")
        conv2 = Conversation(user_id=user.id, title="会话2")
        conv3 = Conversation(user_id=user.id, title="会话3")
        db_session.add_all([conv1, conv2, conv3])
        await db_session.commit()

        # 查询用户并加载会话关系
        result = await db_session.execute(
            select(User).where(User.id == user.id).options(selectinload(User.conversations))
        )
        user_with_convs = result.scalar_one()

        assert len(user_with_convs.conversations) == 3
        titles = [c.title for c in user_with_convs.conversations]
        assert "会话1" in titles
        assert "会话2" in titles
        assert "会话3" in titles

    @pytest.mark.asyncio
    async def test_conversation_user_relationship(self, db_session: AsyncSession):
        """测试会话与用户的反向关系"""
        user = User(
            username="backrefuser",
            email="backrefuser@example.com",
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

        # 通过会话访问用户
        assert conversation.user is not None
        assert conversation.user.username == "backrefuser"

    @pytest.mark.asyncio
    async def test_conversation_cascade_delete(self, db_session: AsyncSession):
        """测试删除用户时级联删除会话"""
        user = User(
            username="cascadedelete",
            email="cascadedelete@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        user_id = user.id

        # 创建会话
        conv = Conversation(
            user_id=user_id,
            title="将被删除的会话"
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)
        conv_id = conv.id

        # 删除用户
        await db_session.delete(user)
        await db_session.commit()

        # 检查会话是否被删除
        result = await db_session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        deleted_conv = result.scalar_one_or_none()
        assert deleted_conv is None

    @pytest.mark.asyncio
    async def test_conversation_updated_at(self, db_session: AsyncSession):
        """测试 updated_at 字段自动更新"""
        user = User(
            username="updatetime",
            email="updatetime@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        conversation = Conversation(
            user_id=user.id,
            title="更新时间测试"
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        original_updated_at = conversation.updated_at

        # 更新会话标题
        conversation.title = "更新后的标题"
        await db_session.commit()
        await db_session.refresh(conversation)

        # updated_at 应该已更新
        assert conversation.updated_at >= original_updated_at

    @pytest.mark.asyncio
    async def test_query_conversations_by_user(self, db_session: AsyncSession):
        """测试按用户查询会话"""
        # 创建两个用户
        user1 = User(username="queryuser1", email="queryuser1@example.com", password_hash="hash")
        user2 = User(username="queryuser2", email="queryuser2@example.com", password_hash="hash")
        db_session.add_all([user1, user2])
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)

        # 为每个用户创建会话
        conv1 = Conversation(user_id=user1.id, title="用户1的会话")
        conv2 = Conversation(user_id=user1.id, title="用户1的另一个会话")
        conv3 = Conversation(user_id=user2.id, title="用户2的会话")
        db_session.add_all([conv1, conv2, conv3])
        await db_session.commit()

        # 查询 user1 的会话
        result = await db_session.execute(
            select(Conversation).where(Conversation.user_id == user1.id)
        )
        user1_convs = result.scalars().all()

        assert len(user1_convs) == 2
        for conv in user1_convs:
            assert conv.user_id == user1.id

    @pytest.mark.asyncio
    async def test_conversation_repr(self, db_session: AsyncSession):
        """测试会话的字符串表示"""
        user = User(
            username="repruser",
            email="repruser@example.com",
            password_hash="hash"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        conversation = Conversation(
            user_id=user.id,
            title="_repr测试"
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        repr_str = repr(conversation)
        assert "Conversation" in repr_str
        assert str(conversation.id) in repr_str
        assert str(conversation.user_id) in repr_str
        assert "repr测试" in repr_str
