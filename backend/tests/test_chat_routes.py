"""
对话 API 路由测试
测试 POST /api/chat、GET /api/chat/history、DELETE /api/chat/history
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from backend.main import app
from backend.database import Base, get_db
from backend.models.user import User, ChatHistory
from backend.services.auth import hash_password, create_access_token


# ==================== 测试数据库配置 ====================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_session(test_engine):
    """创建测试数据库会话"""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


@pytest.fixture(scope="function")
async def test_client(test_session):
    """创建测试客户端"""
    async def override_get_db():
        yield test_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(test_session: AsyncSession):
    """创建测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("password123"),
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User):
    """生成认证请求头"""
    token = create_access_token(
        data={"sub": test_user.id, "username": test_user.username}
    )
    return {"Authorization": f"Bearer {token}"}


# ==================== 测试用例 ====================

class TestSendMessage:
    """测试发送消息 API"""

    @pytest.mark.asyncio
    async def test_send_message_success(
        self,
        test_client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """测试成功发送消息"""
        response = await test_client.post(
            "/api/chat",
            json={"content": "你好，这是一条测试消息"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"]["role"] == "user"
        assert data["message"]["content"] == "你好，这是一条测试消息"
        assert "id" in data["message"]
        assert "created_at" in data["message"]

    @pytest.mark.asyncio
    async def test_send_message_empty_content(
        self,
        test_client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """测试发送空消息"""
        response = await test_client.post(
            "/api/chat",
            json={"content": ""},
            headers=auth_headers,
        )
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_send_message_too_long(
        self,
        test_client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """测试发送超长消息"""
        response = await test_client.post(
            "/api/chat",
            json={"content": "a" * 10001},
            headers=auth_headers,
        )
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_send_message_without_auth(
        self,
        test_client: AsyncClient,
    ):
        """测试未认证发送消息"""
        response = await test_client.post(
            "/api/chat",
            json={"content": "测试消息"},
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_send_message_saved_to_db(
        self,
        test_client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """测试消息正确保存到数据库"""
        response = await test_client.post(
            "/api/chat",
            json={"content": "保存测试"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        message_id = response.json()["message"]["id"]
        
        # 验证数据库中存在该消息
        result = await test_session.execute(
            select(ChatHistory).where(ChatHistory.id == message_id)
        )
        saved_msg = result.scalar_one()
        assert saved_msg is not None
        assert saved_msg.content == "保存测试"
        assert saved_msg.role == "user"
        assert saved_msg.user_id == test_user.id


class TestGetChatHistory:
    """测试获取聊天历史 API"""

    @pytest.mark.asyncio
    async def test_get_history_empty(
        self,
        test_client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """测试获取空历史记录"""
        response = await test_client.get(
            "/api/chat/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["messages"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_history_with_messages(
        self,
        test_client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """测试获取有消息的历史记录"""
        # 创建一些测试消息
        for i in range(5):
            user_msg = ChatHistory(
                user_id=test_user.id,
                role="user",
                content=f"用户消息 {i}",
            )
            assistant_msg = ChatHistory(
                user_id=test_user.id,
                role="assistant",
                content=f"助手回复 {i}",
            )
            test_session.add(user_msg)
            test_session.add(assistant_msg)
        await test_session.commit()
        
        response = await test_client.get(
            "/api/chat/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["messages"]) == 10  # 5 对话
        assert data["total"] == 10
        # 消息按时间正序排列
        assert data["messages"][0]["content"] == "用户消息 0"

    @pytest.mark.asyncio
    async def test_get_history_pagination(
        self,
        test_client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """测试分页获取历史记录"""
        # 创建 25 条消息
        for i in range(25):
            msg = ChatHistory(
                user_id=test_user.id,
                role="user",
                content=f"消息 {i}",
            )
            test_session.add(msg)
        await test_session.commit()
        
        # 获取第一页
        response = await test_client.get(
            "/api/chat/history?page=1&page_size=10",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 10
        assert data["has_more"] is True
        assert data["page"] == 1
        
        # 获取第二页
        response = await test_client.get(
            "/api/chat/history?page=2&page_size=10",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 10

    @pytest.mark.asyncio
    async def test_get_history_with_before_id(
        self,
        test_client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """测试使用游标分页（before_id）"""
        # 创建消息
        message_ids = []
        for i in range(15):
            msg = ChatHistory(
                user_id=test_user.id,
                role="user",
                content=f"游标消息 {i}",
            )
            test_session.add(msg)
            await test_session.flush()
            message_ids.append(msg.id)
        await test_session.commit()
        
        # 使用 before_id 获取更早的消息
        middle_id = message_ids[7]  # 从中间开始
        
        response = await test_client.get(
            f"/api/chat/history?before_id={middle_id}&page_size=5",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        # 应该获取到比 middle_id 更小的消息（更早的消息）
        for msg in data["messages"]:
            assert msg["id"] < middle_id

    @pytest.mark.asyncio
    async def test_get_history_without_auth(
        self,
        test_client: AsyncClient,
    ):
        """测试未认证获取历史"""
        response = await test_client.get("/api/chat/history")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_history_only_own_messages(
        self,
        test_client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """测试只能获取自己的消息"""
        # 创建另一个用户的消息
        other_user = User(
            username="otheruser",
            email="other@example.com",
            password_hash=hash_password("password123"),
        )
        test_session.add(other_user)
        await test_session.flush()
        
        other_msg = ChatHistory(
            user_id=other_user.id,
            role="user",
            content="其他用户的消息",
        )
        test_session.add(other_msg)
        
        # 创建当前用户的消息
        my_msg = ChatHistory(
            user_id=test_user.id,
            role="user",
            content="我的消息",
        )
        test_session.add(my_msg)
        await test_session.commit()
        
        response = await test_client.get(
            "/api/chat/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "我的消息"


class TestClearChatHistory:
    """测试清空聊天历史 API"""

    @pytest.mark.asyncio
    async def test_clear_history_success(
        self,
        test_client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """测试成功清空历史记录"""
        # 创建一些消息
        for i in range(5):
            msg = ChatHistory(
                user_id=test_user.id,
                role="user",
                content=f"消息 {i}",
            )
            test_session.add(msg)
        await test_session.commit()
        
        response = await test_client.delete(
            "/api/chat/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 5
        
        # 验证数据库中已清空
        result = await test_session.execute(
            select(ChatHistory).where(ChatHistory.user_id == test_user.id)
        )
        messages = result.scalars().all()
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_clear_history_empty(
        self,
        test_client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """测试清空空历史记录"""
        response = await test_client.delete(
            "/api/chat/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 0

    @pytest.mark.asyncio
    async def test_clear_history_only_own_messages(
        self,
        test_client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """测试清空只删除自己的消息"""
        # 创建另一个用户
        other_user = User(
            username="otheruser2",
            email="other2@example.com",
            password_hash=hash_password("password123"),
        )
        test_session.add(other_user)
        await test_session.flush()
        
        # 创建两个用户的消息
        for i in range(3):
            my_msg = ChatHistory(
                user_id=test_user.id,
                role="user",
                content=f"我的消息 {i}",
            )
            other_msg = ChatHistory(
                user_id=other_user.id,
                role="user",
                content=f"其他用户消息 {i}",
            )
            test_session.add(my_msg)
            test_session.add(other_msg)
        await test_session.commit()
        
        # 清空当前用户的历史
        response = await test_client.delete(
            "/api/chat/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        assert response.json()["deleted_count"] == 3
        
        # 验证其他用户的消息还在
        result = await test_session.execute(
            select(ChatHistory).where(ChatHistory.user_id == other_user.id)
        )
        other_messages = result.scalars().all()
        assert len(other_messages) == 3

    @pytest.mark.asyncio
    async def test_clear_history_without_auth(
        self,
        test_client: AsyncClient,
    ):
        """测试未认证清空历史"""
        response = await test_client.delete("/api/chat/history")
        
        assert response.status_code == 401


class TestChatHistoryIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_send_and_retrieve_flow(
        self,
        test_client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """测试发送消息后获取历史的完整流程"""
        # 发送多条消息
        for i in range(3):
            response = await test_client.post(
                "/api/chat",
                json={"content": f"测试消息 {i}"},
                headers=auth_headers,
            )
            assert response.status_code == 200
        
        # 获取历史记录
        response = await test_client.get(
            "/api/chat/history",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 3
        assert data["messages"][0]["content"] == "测试消息 0"
        assert data["messages"][1]["content"] == "测试消息 1"
        assert data["messages"][2]["content"] == "测试消息 2"

    @pytest.mark.asyncio
    async def test_clear_and_verify_empty(
        self,
        test_client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """测试清空后验证历史为空"""
        # 发送消息
        await test_client.post(
            "/api/chat",
            json={"content": "要清空的消息"},
            headers=auth_headers,
        )
        
        # 清空历史
        await test_client.delete(
            "/api/chat/history",
            headers=auth_headers,
        )
        
        # 验证历史为空
        response = await test_client.get(
            "/api/chat/history",
            headers=auth_headers,
        )
        
        assert response.json()["messages"] == []
