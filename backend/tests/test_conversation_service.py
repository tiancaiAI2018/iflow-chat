"""
测试 ConversationService 服务层
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.database import Base
from backend.models.user import User, Conversation, ChatHistory
from backend.services.conversation_service import (
    ConversationService,
    conversation_to_response,
    chat_history_to_response,
)
from backend.models.schemas import ConversationResponse, ChatMessageResponse


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


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """创建测试用户"""
    user = User(
        username="testuser",
        email="testuser@example.com",
        password_hash="testhash"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user2(db_session: AsyncSession):
    """创建第二个测试用户（用于权限测试）"""
    user = User(
        username="testuser2",
        email="testuser2@example.com",
        password_hash="testhash2"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestConversationService:
    """ConversationService 测试类"""

    @pytest.mark.asyncio
    async def test_create_conversation_default_title(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试创建会话（默认标题）"""
        service = ConversationService(db_session)
        
        conversation = await service.create_conversation(test_user.id)
        
        assert conversation.id is not None
        assert conversation.user_id == test_user.id
        assert conversation.title == "新会话"
        assert conversation.iflow_session_id is None
        assert conversation.created_at is not None
        assert conversation.updated_at is not None

    @pytest.mark.asyncio
    async def test_create_conversation_custom_title(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试创建会话（自定义标题）"""
        service = ConversationService(db_session)
        
        conversation = await service.create_conversation(
            test_user.id, title="自定义标题"
        )
        
        assert conversation.title == "自定义标题"

    @pytest.mark.asyncio
    async def test_create_conversation_with_first_message(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试创建会话（带首条消息，AI 生成标题）"""
        service = ConversationService(db_session)
        
        # Mock AI 标题生成
        with patch.object(
            service, 
            'generate_title_from_message', 
            new_callable=AsyncMock,
            return_value="AI生成的标题"
        ):
            conversation = await service.create_conversation(
                test_user.id, first_message="你好，请帮我写一篇文章"
            )
        
        assert conversation.title == "AI生成的标题"

    @pytest.mark.asyncio
    async def test_get_user_conversations(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试获取用户会话列表"""
        service = ConversationService(db_session)
        
        # 创建多个会话
        await service.create_conversation(test_user.id, title="会话1")
        await service.create_conversation(test_user.id, title="会话2")
        await service.create_conversation(test_user.id, title="会话3")
        
        conversations, total = await service.get_user_conversations(test_user.id)
        
        assert total == 3
        assert len(conversations) == 3
        # 应按更新时间倒序
        titles = [c.title for c in conversations]
        assert "会话1" in titles
        assert "会话2" in titles
        assert "会话3" in titles

    @pytest.mark.asyncio
    async def test_get_user_conversations_pagination(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试获取用户会话列表分页"""
        service = ConversationService(db_session)
        
        # 创建 5 个会话
        for i in range(5):
            await service.create_conversation(test_user.id, title=f"会话{i+1}")
        
        # 获取第一页
        conversations, total = await service.get_user_conversations(
            test_user.id, limit=2, offset=0
        )
        assert total == 5
        assert len(conversations) == 2
        
        # 获取第二页
        conversations, total = await service.get_user_conversations(
            test_user.id, limit=2, offset=2
        )
        assert len(conversations) == 2

    @pytest.mark.asyncio
    async def test_get_user_conversations_empty(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试获取空会话列表"""
        service = ConversationService(db_session)
        
        conversations, total = await service.get_user_conversations(test_user.id)
        
        assert total == 0
        assert len(conversations) == 0

    @pytest.mark.asyncio
    async def test_get_user_conversations_only_own(
        self, db_session: AsyncSession, test_user: User, test_user2: User
    ):
        """测试用户只能看到自己的会话"""
        service = ConversationService(db_session)
        
        # 为两个用户创建会话
        await service.create_conversation(test_user.id, title="用户1的会话")
        await service.create_conversation(test_user2.id, title="用户2的会话")
        
        # 用户1 查询
        conversations, total = await service.get_user_conversations(test_user.id)
        assert total == 1
        assert conversations[0].title == "用户1的会话"
        
        # 用户2 查询
        conversations, total = await service.get_user_conversations(test_user2.id)
        assert total == 1
        assert conversations[0].title == "用户2的会话"

    @pytest.mark.asyncio
    async def test_get_conversation(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试获取单个会话"""
        service = ConversationService(db_session)
        
        created = await service.create_conversation(test_user.id, title="测试会话")
        
        conversation = await service.get_conversation(created.id, test_user.id)
        
        assert conversation is not None
        assert conversation.id == created.id
        assert conversation.title == "测试会话"

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试获取不存在的会话"""
        service = ConversationService(db_session)
        
        conversation = await service.get_conversation(99999, test_user.id)
        
        assert conversation is None

    @pytest.mark.asyncio
    async def test_get_conversation_wrong_user(
        self, db_session: AsyncSession, test_user: User, test_user2: User
    ):
        """测试获取其他用户的会话（应返回 None）"""
        service = ConversationService(db_session)
        
        created = await service.create_conversation(test_user.id, title="用户1的会话")
        
        # 用户2 尝试访问用户1的会话
        conversation = await service.get_conversation(created.id, test_user2.id)
        
        assert conversation is None

    @pytest.mark.asyncio
    async def test_get_conversation_with_messages(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试获取会话详情及消息"""
        service = ConversationService(db_session)
        
        # 创建会话
        conversation = await service.create_conversation(test_user.id, title="带消息的会话")
        
        # 添加消息
        msg1 = ChatHistory(
            user_id=test_user.id,
            conversation_id=conversation.id,
            role="user",
            content="你好"
        )
        msg2 = ChatHistory(
            user_id=test_user.id,
            conversation_id=conversation.id,
            role="assistant",
            content="你好！有什么可以帮助你的？"
        )
        db_session.add_all([msg1, msg2])
        await db_session.commit()
        
        # 获取会话和消息
        result = await service.get_conversation_with_messages(conversation.id, test_user.id)
        
        assert result is not None
        conv, messages = result
        assert conv.id == conversation.id
        assert len(messages) == 2
        assert messages[0].content == "你好"
        assert messages[1].content == "你好！有什么可以帮助你的？"

    @pytest.mark.asyncio
    async def test_get_conversation_with_messages_empty(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试获取会话详情（无消息）"""
        service = ConversationService(db_session)
        
        conversation = await service.create_conversation(test_user.id, title="空会话")
        
        result = await service.get_conversation_with_messages(conversation.id, test_user.id)
        
        assert result is not None
        conv, messages = result
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_delete_conversation(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试删除会话"""
        service = ConversationService(db_session)
        
        conversation = await service.create_conversation(test_user.id, title="要删除的会话")
        
        # 删除
        result = await service.delete_conversation(conversation.id, test_user.id)
        
        assert result is True
        
        # 验证已删除
        deleted = await service.get_conversation(conversation.id, test_user.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delete_conversation_with_messages(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试删除会话及其消息（级联删除）"""
        service = ConversationService(db_session)
        
        # 创建会话和消息
        conversation = await service.create_conversation(test_user.id, title="带消息的会话")
        msg = ChatHistory(
            user_id=test_user.id,
            conversation_id=conversation.id,
            role="user",
            content="测试消息"
        )
        db_session.add(msg)
        await db_session.commit()
        
        # 删除会话
        result = await service.delete_conversation(conversation.id, test_user.id)
        
        assert result is True
        
        # 验证消息也被删除
        query = select(ChatHistory).where(ChatHistory.conversation_id == conversation.id)
        msg_result = await db_session.execute(query)
        messages = msg_result.scalars().all()
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_delete_conversation_wrong_user(
        self, db_session: AsyncSession, test_user: User, test_user2: User
    ):
        """测试删除其他用户的会话（应失败）"""
        service = ConversationService(db_session)
        
        conversation = await service.create_conversation(test_user.id, title="用户1的会话")
        
        # 用户2 尝试删除用户1的会话
        result = await service.delete_conversation(conversation.id, test_user2.id)
        
        assert result is False
        
        # 验证会话仍然存在
        still_exists = await service.get_conversation(conversation.id, test_user.id)
        assert still_exists is not None

    @pytest.mark.asyncio
    async def test_update_conversation_title(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试更新会话标题"""
        service = ConversationService(db_session)
        
        conversation = await service.create_conversation(test_user.id, title="原标题")
        
        updated = await service.update_conversation_title(
            conversation.id, test_user.id, "新标题"
        )
        
        assert updated is not None
        assert updated.title == "新标题"

    @pytest.mark.asyncio
    async def test_update_conversation_title_wrong_user(
        self, db_session: AsyncSession, test_user: User, test_user2: User
    ):
        """测试更新其他用户的会话标题（应失败）"""
        service = ConversationService(db_session)
        
        conversation = await service.create_conversation(test_user.id, title="用户1的会话")
        
        updated = await service.update_conversation_title(
            conversation.id, test_user2.id, "恶意修改"
        )
        
        assert updated is None
        
        # 验证标题未改变
        still_same = await service.get_conversation(conversation.id, test_user.id)
        assert still_same.title == "用户1的会话"

    @pytest.mark.asyncio
    async def test_update_conversation_iflow_session(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试更新会话的 iFlow session ID"""
        service = ConversationService(db_session)
        
        conversation = await service.create_conversation(test_user.id, title="测试会话")
        
        updated = await service.update_conversation_iflow_session(
            conversation.id, test_user.id, "iflow-session-123"
        )
        
        assert updated is not None
        assert updated.iflow_session_id == "iflow-session-123"

    @pytest.mark.asyncio
    async def test_touch_conversation(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试更新会话时间戳"""
        service = ConversationService(db_session)
        
        conversation = await service.create_conversation(test_user.id, title="测试会话")
        original_updated_at = conversation.updated_at
        
        # 稍微等待
        import asyncio
        await asyncio.sleep(0.01)
        
        result = await service.touch_conversation(conversation.id, test_user.id)
        
        assert result is True
        
        # 刷新并检查时间戳已更新
        await db_session.refresh(conversation)
        assert conversation.updated_at > original_updated_at

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_existing(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试获取或创建会话（已存在）"""
        service = ConversationService(db_session)
        
        created = await service.create_conversation(test_user.id, title="已存在的会话")
        
        result = await service.get_or_create_conversation(test_user.id, created.id)
        
        assert result.id == created.id
        assert result.title == "已存在的会话"

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_create_new(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试获取或创建会话（创建新的）"""
        service = ConversationService(db_session)
        
        # 不提供 conversation_id，应创建新会话
        result = await service.get_or_create_conversation(test_user.id)
        
        assert result.id is not None
        assert result.title == "新会话"

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_invalid_id(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试获取或创建会话（无效 ID，创建新的）"""
        service = ConversationService(db_session)
        
        # 提供不存在的 conversation_id
        result = await service.get_or_create_conversation(test_user.id, 99999)
        
        assert result.id is not None
        assert result.title == "新会话"

    @pytest.mark.asyncio
    async def test_generate_title_from_message(
        self, db_session: AsyncSession
    ):
        """测试 AI 生成标题"""
        service = ConversationService(db_session)
        
        # Mock IFlowClientService
        with patch('backend.services.conversation_service.IFlowClientService') as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.query = AsyncMock(return_value="这是一个测试标题")
            MockClient.return_value = mock_instance
            
            title = await service.generate_title_from_message("你好，请帮我写一篇文章")
            
            assert title == "这是一个测试标题"

    @pytest.mark.asyncio
    async def test_generate_title_from_message_empty(
        self, db_session: AsyncSession
    ):
        """测试空消息生成标题"""
        service = ConversationService(db_session)
        
        title = await service.generate_title_from_message("")
        
        assert title == "新会话"

    @pytest.mark.asyncio
    async def test_generate_title_from_message_long(
        self, db_session: AsyncSession
    ):
        """测试长消息生成标题（截断）"""
        service = ConversationService(db_session)
        
        # Mock 返回一个超长标题
        with patch('backend.services.conversation_service.IFlowClientService') as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.query = AsyncMock(return_value="这是一个非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的标题")
            MockClient.return_value = mock_instance
            
            title = await service.generate_title_from_message("测试消息")
            
            # 应被截断到 50 字符
            assert len(title) <= 50

    @pytest.mark.asyncio
    async def test_generate_title_from_message_fallback(
        self, db_session: AsyncSession
    ):
        """测试 AI 生成标题失败时的回退"""
        service = ConversationService(db_session)
        
        # Mock 抛出异常
        with patch('backend.services.conversation_service.IFlowClientService') as MockClient:
            MockClient.side_effect = Exception("Connection error")
            
            title = await service.generate_title_from_message("这是一条很长的测试消息内容")
            
            # 应回退到消息前 20 字符
            assert "这是一条很长的测试消息内容"[:20] in title


class TestHelperFunctions:
    """辅助函数测试"""

    def test_conversation_to_response(self, test_user: User):
        """测试会话转响应模型"""
        conversation = Conversation(
            id=1,
            user_id=test_user.id,
            title="测试会话",
            iflow_session_id="session-123",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        response = conversation_to_response(conversation)
        
        assert isinstance(response, ConversationResponse)
        assert response.id == 1
        assert response.title == "测试会话"
        assert response.iflow_session_id == "session-123"

    def test_chat_history_to_response(self):
        """测试聊天历史转响应模型"""
        message = ChatHistory(
            id=1,
            user_id=1,
            conversation_id=1,
            role="user",
            content="测试消息",
            created_at=datetime.now(timezone.utc),
        )
        
        response = chat_history_to_response(message)
        
        assert isinstance(response, ChatMessageResponse)
        assert response.id == 1
        assert response.role == "user"
        assert response.content == "测试消息"
