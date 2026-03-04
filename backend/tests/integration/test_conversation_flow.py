"""
iFlow 对话网页应用 - 会话功能集成测试

测试完整的会话流程：
- 创建会话
- 获取会话列表
- 切换会话并获取历史
- 删除会话
- 更新会话标题
- 会话与消息关联
"""
import pytest
import asyncio
import json
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import get_db, Base
from backend.models.user import User, Conversation, ChatHistory
from backend.models.schemas import (
    ConversationCreate,
    ConversationResponse,
)
from backend.services.auth import create_access_token, hash_password
from backend.services.conversation_service import ConversationService
from backend.routers import conversations, chat


# ==================== 创建测试应用 ====================

def create_test_app():
    """创建测试用 FastAPI 应用"""
    test_app = FastAPI(
        title="iFlow Chat API (Test)",
        description="测试用应用",
        version="1.0.0",
    )
    
    # CORS 配置
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    test_app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
    test_app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    
    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    return test_app


# ==================== Fixtures ====================

@pytest.fixture(scope="function")
async def db_session():
    """创建测试数据库会话（使用内存数据库）"""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    
    # 创建表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建会话
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with test_session_maker() as session:
        yield session
    
    # 清理
    await test_engine.dispose()


@pytest.fixture(scope="function")
async def client(db_session):
    """创建测试客户端"""
    test_app = create_test_app()
    
    async def override_get_db():
        yield db_session
    
    test_app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    test_app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """创建测试用户"""
    user = User(
        username="convuser",
        email="conv@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user: User):
    """生成认证 Token"""
    return create_access_token({"sub": test_user.id, "username": test_user.username})


@pytest.fixture
def auth_headers(auth_token: str):
    """生成认证请求头"""
    return {"Authorization": f"Bearer {auth_token}"}


# ==================== 创建会话流程测试 ====================

@pytest.mark.asyncio
class TestCreateConversationFlow:
    """创建会话流程测试"""
    
    async def test_create_conversation_without_title(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """测试创建会话（无标题，默认'新会话'）"""
        response = await client.post(
            "/api/conversations/",
            headers=auth_headers,
            json={},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["conversation"]["title"] == "新会话"
        assert data["conversation"]["user_id"] == test_user.id
        assert data["messages"] == []
    
    async def test_create_conversation_with_title(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """测试创建会话（自定义标题）"""
        response = await client.post(
            "/api/conversations/",
            headers=auth_headers,
            json={"title": "我的第一个会话"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["conversation"]["title"] == "我的第一个会话"
    
    async def test_create_conversation_with_first_message(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """测试创建会话（提供首条消息，AI 生成标题）"""
        # Mock AI 标题生成
        with patch.object(
            ConversationService,
            'generate_title_from_message',
            new_callable=AsyncMock,
            return_value="关于编程的问题"
        ):
            response = await client.post(
                "/api/conversations/",
                headers=auth_headers,
                json={"first_message": "请帮我解释什么是 Python 的装饰器？"},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["conversation"]["title"] == "关于编程的问题"
    
    async def test_create_conversation_title_overrides_first_message(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """测试创建会话（同时提供标题和首条消息，标题优先）"""
        with patch.object(
            ConversationService,
            'generate_title_from_message',
            new_callable=AsyncMock,
            return_value="AI 生成的标题"
        ):
            response = await client.post(
                "/api/conversations/",
                headers=auth_headers,
                json={
                    "title": "用户指定的标题",
                    "first_message": "这是首条消息"
                },
            )
            
            assert response.status_code == 200
            data = response.json()
            # 标题优先，不调用 AI 生成
            assert data["conversation"]["title"] == "用户指定的标题"


# ==================== 获取会话列表测试 ====================

@pytest.mark.asyncio
class TestGetConversationsFlow:
    """获取会话列表测试"""
    
    async def test_get_empty_conversations_list(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试获取空会话列表"""
        response = await client.get(
            "/api/conversations/",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["conversations"] == []
        assert data["total"] == 0
    
    async def test_get_conversations_list(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试获取会话列表"""
        # 创建多个会话
        for i in range(3):
            conv = Conversation(
                user_id=test_user.id,
                title=f"会话 {i+1}",
            )
            db_session.add(conv)
        await db_session.commit()
        
        response = await client.get(
            "/api/conversations/",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["conversations"]) == 3
        assert data["total"] == 3
    
    async def test_conversations_ordered_by_updated_at(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试会话按更新时间倒序排列"""
        import time
        
        # 创建会话，有时间间隔
        conv1 = Conversation(user_id=test_user.id, title="第一个会话")
        db_session.add(conv1)
        await db_session.commit()
        
        await asyncio.sleep(0.1)  # 确保时间差
        
        conv2 = Conversation(user_id=test_user.id, title="第二个会话")
        db_session.add(conv2)
        await db_session.commit()
        
        response = await client.get(
            "/api/conversations/",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        # 最新的会话在前
        assert data["conversations"][0]["title"] == "第二个会话"
        assert data["conversations"][1]["title"] == "第一个会话"
    
    async def test_conversations_pagination(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试会话列表分页"""
        # 创建 15 个会话
        for i in range(15):
            conv = Conversation(
                user_id=test_user.id,
                title=f"会话 {i+1}",
            )
            db_session.add(conv)
        await db_session.commit()
        
        # 获取第一页
        response = await client.get(
            "/api/conversations/?limit=10&offset=0",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 10
        assert data["total"] == 15
        
        # 获取第二页
        response = await client.get(
            "/api/conversations/?limit=10&offset=10",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 5
    
    async def test_only_own_conversations(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试只能获取自己的会话"""
        # 创建另一个用户
        other_user = User(
            username="otheruser",
            email="other@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        # 创建其他用户的会话
        other_conv = Conversation(
            user_id=other_user.id,
            title="其他用户的会话",
        )
        db_session.add(other_conv)
        
        # 创建当前用户的会话
        my_conv = Conversation(
            user_id=test_user.id,
            title="我的会话",
        )
        db_session.add(my_conv)
        await db_session.commit()
        
        response = await client.get(
            "/api/conversations/",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["conversations"][0]["title"] == "我的会话"


# ==================== 切换会话并获取历史测试 ====================

@pytest.mark.asyncio
class TestSwitchConversationAndGetHistory:
    """切换会话并获取历史测试"""
    
    async def test_get_conversation_detail(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试获取会话详情"""
        # 创建会话
        conv = Conversation(
            user_id=test_user.id,
            title="测试会话",
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)
        
        response = await client.get(
            f"/api/conversations/{conv.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["conversation"]["title"] == "测试会话"
        assert data["messages"] == []
    
    async def test_get_conversation_with_messages(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试获取会话详情及其消息历史"""
        # 创建会话
        conv = Conversation(
            user_id=test_user.id,
            title="有消息的会话",
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)
        
        # 创建消息
        messages = [
            ChatHistory(
                user_id=test_user.id,
                conversation_id=conv.id,
                role="user",
                content="你好",
            ),
            ChatHistory(
                user_id=test_user.id,
                conversation_id=conv.id,
                role="assistant",
                content="你好！有什么可以帮助你的？",
            ),
        ]
        for msg in messages:
            db_session.add(msg)
        await db_session.commit()
        
        response = await client.get(
            f"/api/conversations/{conv.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "你好"
        assert data["messages"][1]["role"] == "assistant"
    
    async def test_get_nonexistent_conversation(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试获取不存在的会话"""
        response = await client.get(
            "/api/conversations/99999",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
    
    async def test_get_other_user_conversation(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试获取其他用户的会话（无权限）"""
        # 创建另一个用户
        other_user = User(
            username="otheruser2",
            email="other2@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        # 创建其他用户的会话
        other_conv = Conversation(
            user_id=other_user.id,
            title="其他用户的会话",
        )
        db_session.add(other_conv)
        await db_session.commit()
        await db_session.refresh(other_conv)
        
        response = await client.get(
            f"/api/conversations/{other_conv.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
    
    async def test_messages_ordered_by_time(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试消息按时间正序排列"""
        # 创建会话
        conv = Conversation(
            user_id=test_user.id,
            title="消息顺序测试",
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)
        
        # 创建消息
        for i in range(3):
            msg = ChatHistory(
                user_id=test_user.id,
                conversation_id=conv.id,
                role="user",
                content=f"消息_{i}",
            )
            db_session.add(msg)
            await db_session.commit()
        
        response = await client.get(
            f"/api/conversations/{conv.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        contents = [m["content"] for m in data["messages"]]
        assert contents == ["消息_0", "消息_1", "消息_2"]


# ==================== 删除会话测试 ====================

@pytest.mark.asyncio
class TestDeleteConversationFlow:
    """删除会话测试"""
    
    async def test_delete_conversation(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试删除会话"""
        # 创建会话
        conv = Conversation(
            user_id=test_user.id,
            title="要删除的会话",
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)
        
        # 删除会话
        response = await client.delete(
            f"/api/conversations/{conv.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "删除成功" in data["message"]
        
        # 验证会话已被删除
        response = await client.get(
            f"/api/conversations/{conv.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404
    
    async def test_delete_conversation_cascades_messages(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试删除会话级联删除消息"""
        # 创建会话
        conv = Conversation(
            user_id=test_user.id,
            title="带消息的会话",
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)
        
        # 创建消息
        for i in range(3):
            msg = ChatHistory(
                user_id=test_user.id,
                conversation_id=conv.id,
                role="user",
                content=f"消息_{i}",
            )
            db_session.add(msg)
        await db_session.commit()
        
        # 删除会话
        response = await client.delete(
            f"/api/conversations/{conv.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        
        # 验证消息也被删除（通过查询 chat history）
        query = select(ChatHistory).where(ChatHistory.conversation_id == conv.id)
        result = await db_session.execute(query)
        messages = result.scalars().all()
        assert len(messages) == 0
    
    async def test_delete_nonexistent_conversation(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试删除不存在的会话"""
        response = await client.delete(
            "/api/conversations/99999",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
    
    async def test_delete_other_user_conversation(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试删除其他用户的会话（无权限）"""
        # 创建另一个用户
        other_user = User(
            username="otheruser3",
            email="other3@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        # 创建其他用户的会话
        other_conv = Conversation(
            user_id=other_user.id,
            title="其他用户的会话",
        )
        db_session.add(other_conv)
        await db_session.commit()
        await db_session.refresh(other_conv)
        
        response = await client.delete(
            f"/api/conversations/{other_conv.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404


# ==================== 更新会话标题测试 ====================

@pytest.mark.asyncio
class TestUpdateConversationTitle:
    """更新会话标题测试"""
    
    async def test_update_conversation_title(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试更新会话标题"""
        # 创建会话
        conv = Conversation(
            user_id=test_user.id,
            title="原始标题",
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)
        
        # 更新标题
        response = await client.put(
            f"/api/conversations/{conv.id}/title",
            headers=auth_headers,
            json={"title": "新标题"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["conversation"]["title"] == "新标题"
        assert "更新成功" in data["message"]
    
    async def test_update_nonexistent_conversation_title(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试更新不存在会话的标题"""
        response = await client.put(
            "/api/conversations/99999/title",
            headers=auth_headers,
            json={"title": "新标题"},
        )
        
        assert response.status_code == 404
    
    async def test_update_other_user_conversation_title(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试更新其他用户会话的标题（无权限）"""
        # 创建另一个用户
        other_user = User(
            username="otheruser4",
            email="other4@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        # 创建其他用户的会话
        other_conv = Conversation(
            user_id=other_user.id,
            title="其他用户的会话",
        )
        db_session.add(other_conv)
        await db_session.commit()
        await db_session.refresh(other_conv)
        
        response = await client.put(
            f"/api/conversations/{other_conv.id}/title",
            headers=auth_headers,
            json={"title": "尝试修改"},
        )
        
        assert response.status_code == 404


# ==================== 会话与消息关联测试 ====================

@pytest.mark.asyncio
class TestConversationMessageAssociation:
    """会话与消息关联测试"""
    
    async def test_message_associated_with_conversation(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试消息正确关联到会话"""
        # 创建两个会话
        conv1 = Conversation(user_id=test_user.id, title="会话1")
        conv2 = Conversation(user_id=test_user.id, title="会话2")
        db_session.add_all([conv1, conv2])
        await db_session.commit()
        await db_session.refresh(conv1)
        await db_session.refresh(conv2)
        
        # 在两个会话中分别创建消息
        msg1 = ChatHistory(
            user_id=test_user.id,
            conversation_id=conv1.id,
            role="user",
            content="会话1的消息",
        )
        msg2 = ChatHistory(
            user_id=test_user.id,
            conversation_id=conv2.id,
            role="user",
            content="会话2的消息",
        )
        db_session.add_all([msg1, msg2])
        await db_session.commit()
        
        # 验证会话1只包含会话1的消息
        response = await client.get(
            f"/api/conversations/{conv1.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "会话1的消息"
        
        # 验证会话2只包含会话2的消息
        response = await client.get(
            f"/api/conversations/{conv2.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "会话2的消息"
    
    async def test_chat_history_by_conversation(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试按会话查询聊天历史"""
        # 创建两个会话
        conv1 = Conversation(user_id=test_user.id, title="会话A")
        conv2 = Conversation(user_id=test_user.id, title="会话B")
        db_session.add_all([conv1, conv2])
        await db_session.commit()
        await db_session.refresh(conv1)
        await db_session.refresh(conv2)
        
        # 在两个会话中分别创建消息
        for i in range(3):
            msg1 = ChatHistory(
                user_id=test_user.id,
                conversation_id=conv1.id,
                role="user",
                content=f"会话A消息_{i}",
            )
            msg2 = ChatHistory(
                user_id=test_user.id,
                conversation_id=conv2.id,
                role="user",
                content=f"会话B消息_{i}",
            )
            db_session.add_all([msg1, msg2])
        await db_session.commit()
        
        # 查询会话1的历史
        response = await client.get(
            f"/api/chat/history?conversation_id={conv1.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["messages"]) == 3
        for msg in data["messages"]:
            assert "会话A消息" in msg["content"]
        
        # 查询会话2的历史
        response = await client.get(
            f"/api/chat/history?conversation_id={conv2.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 3
        for msg in data["messages"]:
            assert "会话B消息" in msg["content"]
    
    async def test_conversation_updated_at_on_new_message(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试新消息更新会话的 updated_at"""
        # 创建会话
        conv = Conversation(
            user_id=test_user.id,
            title="测试会话",
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)
        
        original_updated_at = conv.updated_at
        
        # 等待一小段时间
        await asyncio.sleep(0.1)
        
        # 添加新消息（模拟服务层更新）
        service = ConversationService(db_session)
        await service.touch_conversation(conv.id, test_user.id)
        
        # 重新获取会话
        await db_session.refresh(conv)
        
        # 验证 updated_at 已更新
        assert conv.updated_at > original_updated_at


# ==================== 完整流程测试 ====================

@pytest.mark.asyncio
class TestCompleteConversationFlow:
    """完整会话流程测试"""
    
    async def test_complete_user_journey(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """测试完整用户旅程：创建会话 → 发送消息 → 查看历史 → 切换会话 → 删除会话"""
        
        # 1. 创建第一个会话
        response = await client.post(
            "/api/conversations/",
            headers=auth_headers,
            json={"title": "第一个会话"},
        )
        assert response.status_code == 200
        conv1_id = response.json()["conversation"]["id"]
        
        # 2. 在第一个会话中添加消息
        msg1 = ChatHistory(
            user_id=test_user.id,
            conversation_id=conv1_id,
            role="user",
            content="第一个会话的消息",
        )
        db_session.add(msg1)
        await db_session.commit()
        
        # 3. 创建第二个会话
        response = await client.post(
            "/api/conversations/",
            headers=auth_headers,
            json={"title": "第二个会话"},
        )
        assert response.status_code == 200
        conv2_id = response.json()["conversation"]["id"]
        
        # 4. 在第二个会话中添加消息
        msg2 = ChatHistory(
            user_id=test_user.id,
            conversation_id=conv2_id,
            role="user",
            content="第二个会话的消息",
        )
        db_session.add(msg2)
        await db_session.commit()
        
        # 5. 获取会话列表（应该有2个）
        response = await client.get(
            "/api/conversations/",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()["conversations"]) == 2
        
        # 6. 切换到第一个会话并查看历史
        response = await client.get(
            f"/api/conversations/{conv1_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()["messages"]) == 1
        assert response.json()["messages"][0]["content"] == "第一个会话的消息"
        
        # 7. 删除第一个会话
        response = await client.delete(
            f"/api/conversations/{conv1_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        
        # 8. 再次获取会话列表（应该只剩1个）
        response = await client.get(
            "/api/conversations/",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()["conversations"]) == 1
        assert response.json()["conversations"][0]["id"] == conv2_id
