"""
测试 SQLite 数据库层与 ORM 模型
"""
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from backend.database import Base, engine, async_session_maker
from backend.models.user import User, VerificationCode, ChatHistory


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


@pytest.mark.asyncio
async def test_database_connection(db_session: AsyncSession):
    """测试数据库连接"""
    assert db_session is not None
    # 执行简单查询
    result = await db_session.execute(select(1))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """测试创建用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password_123"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    assert user.id is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.created_at is not None
    assert user.last_login is None


@pytest.mark.asyncio
async def test_user_unique_constraints(db_session: AsyncSession):
    """测试用户唯一约束"""
    user1 = User(
        username="uniqueuser",
        email="unique@example.com",
        password_hash="hash1"
    )
    db_session.add(user1)
    await db_session.commit()
    
    # 尝试创建相同用户名的用户
    user2 = User(
        username="uniqueuser",  # 相同用户名
        email="different@example.com",
        password_hash="hash2"
    )
    db_session.add(user2)
    
    with pytest.raises(Exception):  # 应该抛出 IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_create_verification_code(db_session: AsyncSession):
    """测试创建验证码"""
    code = VerificationCode(
        email="test@example.com",
        code="123456",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    db_session.add(code)
    await db_session.commit()
    await db_session.refresh(code)
    
    assert code.id is not None
    assert code.email == "test@example.com"
    assert code.code == "123456"
    assert code.used is False
    assert code.is_valid() is True


@pytest.mark.asyncio
async def test_verification_code_expiry(db_session: AsyncSession):
    """测试验证码过期"""
    # 创建已过期的验证码
    expired_code = VerificationCode(
        email="expired@example.com",
        code="654321",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)  # 已过期
    )
    db_session.add(expired_code)
    await db_session.commit()
    await db_session.refresh(expired_code)
    
    assert expired_code.is_valid() is False


@pytest.mark.asyncio
async def test_verification_code_used(db_session: AsyncSession):
    """测试验证码已使用"""
    code = VerificationCode(
        email="used@example.com",
        code="111111",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        used=True  # 已使用
    )
    db_session.add(code)
    await db_session.commit()
    await db_session.refresh(code)
    
    assert code.is_valid() is False


@pytest.mark.asyncio
async def test_create_chat_history(db_session: AsyncSession):
    """测试创建对话历史"""
    # 先创建用户
    user = User(
        username="chatuser",
        email="chat@example.com",
        password_hash="hash"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # 创建对话历史
    chat1 = ChatHistory(
        user_id=user.id,
        role="user",
        content="你好"
    )
    chat2 = ChatHistory(
        user_id=user.id,
        role="assistant",
        content="你好！有什么可以帮助你的？"
    )
    db_session.add_all([chat1, chat2])
    await db_session.commit()
    
    # 查询对话历史
    result = await db_session.execute(
        select(ChatHistory).where(ChatHistory.user_id == user.id).order_by(ChatHistory.created_at)
    )
    histories = result.scalars().all()
    
    assert len(histories) == 2
    assert histories[0].role == "user"
    assert histories[0].content == "你好"
    assert histories[1].role == "assistant"


@pytest.mark.asyncio
async def test_user_chat_history_relationship(db_session: AsyncSession):
    """测试用户与对话历史的关系"""
    # 创建用户
    user = User(
        username="relationuser",
        email="relation@example.com",
        password_hash="hash"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # 创建对话历史
    chat = ChatHistory(
        user_id=user.id,
        role="user",
        content="测试关系"
    )
    db_session.add(chat)
    await db_session.commit()
    
    # 使用查询显式加载关系
    result = await db_session.execute(
        select(User).where(User.id == user.id).options(selectinload(User.chat_histories))
    )
    user_with_histories = result.scalar_one()
    assert len(user_with_histories.chat_histories) == 1
    assert user_with_histories.chat_histories[0].content == "测试关系"


@pytest.mark.asyncio
async def test_cascade_delete(db_session: AsyncSession):
    """测试级联删除（删除用户时删除相关对话历史）"""
    # 创建用户
    user = User(
        username="deleteuser",
        email="delete@example.com",
        password_hash="hash"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id
    
    # 创建对话历史
    chat = ChatHistory(
        user_id=user_id,
        role="user",
        content="将被删除"
    )
    db_session.add(chat)
    await db_session.commit()
    
    # 删除用户
    await db_session.delete(user)
    await db_session.commit()
    
    # 检查对话历史是否也被删除
    result = await db_session.execute(
        select(ChatHistory).where(ChatHistory.user_id == user_id)
    )
    histories = result.scalars().all()
    assert len(histories) == 0


@pytest.mark.asyncio
async def test_query_users(db_session: AsyncSession):
    """测试查询用户"""
    # 创建多个用户
    users = [
        User(username=f"user{i}", email=f"user{i}@example.com", password_hash=f"hash{i}")
        for i in range(5)
    ]
    db_session.add_all(users)
    await db_session.commit()
    
    # 查询所有用户
    result = await db_session.execute(select(User))
    all_users = result.scalars().all()
    assert len(all_users) == 5
    
    # 按用户名查询
    result = await db_session.execute(
        select(User).where(User.username == "user2")
    )
    user = result.scalar_one()
    assert user.email == "user2@example.com"
