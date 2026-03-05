"""
iFlow 对话网页应用 - 会话路由测试

测试会话的 CRUD API：创建、查询、删除、更新标题
"""
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.main import app
from backend.database import get_db, Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from backend.models.user import User, Conversation, ChatHistory
from backend.services.auth import create_access_token, hash_password


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
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session):
    """创建测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """生成认证头"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_conversation(db_session, test_user):
    """创建测试会话"""
    conversation = Conversation(
        user_id=test_user.id,
        title="测试会话",
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)
    return conversation


@pytest.fixture
async def test_conversations(db_session, test_user):
    """创建多个测试会话"""
    conversations = []
    for i in range(3):
        conv = Conversation(
            user_id=test_user.id,
            title=f"会话 {i+1}",
        )
        db_session.add(conv)
        conversations.append(conv)
    await db_session.commit()
    for conv in conversations:
        await db_session.refresh(conv)
    return conversations


@pytest.fixture
async def test_messages(db_session, test_conversation):
    """创建测试消息"""
    messages = []
    # 用户消息
    msg1 = ChatHistory(
        user_id=test_conversation.user_id,
        conversation_id=test_conversation.id,
        role="user",
        content="你好",
    )
    db_session.add(msg1)
    messages.append(msg1)
    
    # 助手消息
    msg2 = ChatHistory(
        user_id=test_conversation.user_id,
        conversation_id=test_conversation.id,
        role="assistant",
        content="你好！有什么可以帮助你的吗？",
    )
    db_session.add(msg2)
    messages.append(msg2)
    
    await db_session.commit()
    for msg in messages:
        await db_session.refresh(msg)
    return messages


# ==================== 获取会话列表测试 ====================

@pytest.mark.asyncio
async def test_get_conversations_success(client, test_user, test_conversations):
    """测试获取会话列表成功"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        "/api/conversations/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["conversations"]) == 3
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_get_conversations_empty(client, test_user):
    """测试获取空会话列表"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        "/api/conversations/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["conversations"]) == 0
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_conversations_pagination(client, test_user, test_conversations):
    """测试会话列表分页"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    # 获取第一页（2条）
    response = await client.get(
        "/api/conversations/?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["conversations"]) == 2
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_get_conversations_unauthorized(client):
    """测试未认证获取会话列表"""
    response = await client.get("/api/conversations/")
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_conversations_only_own(client, test_user, db_session):
    """测试只能获取自己的会话"""
    # 创建另一个用户和会话
    other_user = User(
        username="otheruser",
        email="other@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    
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
    
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        "/api/conversations/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["conversations"]) == 1
    assert data["conversations"][0]["title"] == "我的会话"


# ==================== 创建会话测试 ====================

@pytest.mark.asyncio
async def test_create_conversation_success(client, test_user):
    """测试创建会话成功"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.post(
        "/api/conversations/",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "新会话"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["conversation"]["title"] == "新会话"
    assert data["conversation"]["user_id"] == test_user.id
    assert len(data["messages"]) == 0


@pytest.mark.asyncio
async def test_create_conversation_default_title(client, test_user):
    """测试创建会话使用默认标题"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.post(
        "/api/conversations/",
        headers={"Authorization": f"Bearer {token}"},
        json={}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["conversation"]["title"] == "新会话"


@pytest.mark.asyncio
async def test_create_conversation_with_first_message(client, test_user):
    """测试创建会话并使用首条消息生成标题"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    # Mock AI 标题生成
    with patch('backend.services.conversation_service.ConversationService.generate_title_from_message') as mock_gen:
        mock_gen.return_value = "AI生成的标题"
        
        response = await client.post(
            "/api/conversations/",
            headers={"Authorization": f"Bearer {token}"},
            json={"first_message": "帮我写一个 Python 脚本"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["conversation"]["title"] == "AI生成的标题"


@pytest.mark.asyncio
async def test_create_conversation_unauthorized(client):
    """测试未认证创建会话"""
    response = await client.post(
        "/api/conversations/",
        json={"title": "新会话"}
    )
    
    assert response.status_code == 401


# ==================== 创建会话工作目录测试 ====================

@pytest.mark.asyncio
async def test_create_conversation_with_working_directory(client, test_user):
    """测试创建会话时指定工作目录"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.post(
        "/api/conversations/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "指定工作目录的会话",
            "working_directory": "/root/.iflow-bot/workspace/mybot"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["conversation"]["title"] == "指定工作目录的会话"
    assert data["conversation"]["working_directory"] == "/root/.iflow-bot/workspace/mybot"


@pytest.mark.asyncio
async def test_create_conversation_default_working_directory(client, test_user):
    """测试创建会话使用默认工作目录"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.post(
        "/api/conversations/",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "默认工作目录会话"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["conversation"]["working_directory"] == "/root/.iflow-bot/workspace"


@pytest.mark.asyncio
async def test_create_conversation_empty_working_directory(client, test_user):
    """测试创建会话时工作目录为空字符串，应使用默认值"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.post(
        "/api/conversations/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "空工作目录会话",
            "working_directory": ""
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    # 空字符串会被服务层替换为默认值
    assert data["conversation"]["working_directory"] == "/root/.iflow-bot/workspace"


@pytest.mark.asyncio
async def test_conversation_response_includes_working_directory(client, test_user, test_conversation):
    """测试会话响应包含工作目录字段"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        f"/api/conversations/{test_conversation.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "working_directory" in data["conversation"]
    assert data["conversation"]["working_directory"] is not None


@pytest.mark.asyncio
async def test_conversation_list_includes_working_directory(client, test_user, test_conversations):
    """测试会话列表中每个会话都包含工作目录字段"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        "/api/conversations/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    for conv in data["conversations"]:
        assert "working_directory" in conv
        assert conv["working_directory"] is not None


# ==================== 获取会话详情测试 ====================

@pytest.mark.asyncio
async def test_get_conversation_success(client, test_user, test_conversation, test_messages):
    """测试获取会话详情成功"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        f"/api/conversations/{test_conversation.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["conversation"]["id"] == test_conversation.id
    assert data["conversation"]["title"] == "测试会话"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "你好"
    assert data["messages"][1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_get_conversation_not_found(client, test_user):
    """测试获取不存在的会话"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        "/api/conversations/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_conversation_other_user(client, test_user, db_session):
    """测试获取其他用户的会话"""
    # 创建另一个用户和会话
    other_user = User(
        username="otheruser2",
        email="other2@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    
    other_conv = Conversation(
        user_id=other_user.id,
        title="其他用户的会话",
    )
    db_session.add(other_conv)
    await db_session.commit()
    await db_session.refresh(other_conv)
    
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        f"/api/conversations/{other_conv.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_conversation_message_limit(client, test_user, test_conversation, db_session):
    """测试获取会话消息数量限制"""
    # 创建多条消息
    for i in range(10):
        msg = ChatHistory(
            user_id=test_user.id,
            conversation_id=test_conversation.id,
            role="user",
            content=f"消息 {i}",
        )
        db_session.add(msg)
    await db_session.commit()
    
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        f"/api/conversations/{test_conversation.id}?message_limit=5",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 5


@pytest.mark.asyncio
async def test_get_conversation_unauthorized(client, test_conversation):
    """测试未认证获取会话详情"""
    response = await client.get(f"/api/conversations/{test_conversation.id}")
    
    assert response.status_code == 401


# ==================== 删除会话测试 ====================

@pytest.mark.asyncio
async def test_delete_conversation_success(client, test_user, test_conversation, db_session):
    """测试删除会话成功"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.delete(
        f"/api/conversations/{test_conversation.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "会话删除成功"
    
    # 验证会话已被删除
    result = await db_session.execute(
        select(Conversation).where(Conversation.id == test_conversation.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_conversation_with_messages(client, test_user, test_conversation, test_messages, db_session):
    """测试删除会话时级联删除消息"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.delete(
        f"/api/conversations/{test_conversation.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    
    # 验证消息也被删除
    result = await db_session.execute(
        select(ChatHistory).where(ChatHistory.conversation_id == test_conversation.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_conversation_not_found(client, test_user):
    """测试删除不存在的会话"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.delete(
        "/api/conversations/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation_other_user(client, test_user, db_session):
    """测试删除其他用户的会话"""
    # 创建另一个用户和会话
    other_user = User(
        username="otheruser3",
        email="other3@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    
    other_conv = Conversation(
        user_id=other_user.id,
        title="其他用户的会话",
    )
    db_session.add(other_conv)
    await db_session.commit()
    await db_session.refresh(other_conv)
    
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.delete(
        f"/api/conversations/{other_conv.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    
    # 验证会话未被删除
    result = await db_session.execute(
        select(Conversation).where(Conversation.id == other_conv.id)
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_delete_conversation_unauthorized(client, test_conversation):
    """测试未认证删除会话"""
    response = await client.delete(f"/api/conversations/{test_conversation.id}")
    
    assert response.status_code == 401


# ==================== 更新会话标题测试 ====================

@pytest.mark.asyncio
async def test_update_conversation_title_success(client, test_user, test_conversation, db_session):
    """测试更新会话标题成功"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.put(
        f"/api/conversations/{test_conversation.id}/title",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "更新后的标题"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["conversation"]["title"] == "更新后的标题"
    assert data["message"] == "标题更新成功"
    
    # 验证数据库中已更新
    await db_session.refresh(test_conversation)
    assert test_conversation.title == "更新后的标题"


@pytest.mark.asyncio
async def test_update_conversation_title_not_found(client, test_user):
    """测试更新不存在的会话标题"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.put(
        "/api/conversations/99999/title",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "新标题"}
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_conversation_title_other_user(client, test_user, db_session):
    """测试更新其他用户的会话标题"""
    # 创建另一个用户和会话
    other_user = User(
        username="otheruser4",
        email="other4@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    
    other_conv = Conversation(
        user_id=other_user.id,
        title="其他用户的会话",
    )
    db_session.add(other_conv)
    await db_session.commit()
    await db_session.refresh(other_conv)
    
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.put(
        f"/api/conversations/{other_conv.id}/title",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "尝试修改"}
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_conversation_title_empty(client, test_user, test_conversation):
    """测试更新会话标题为空"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.put(
        f"/api/conversations/{test_conversation.id}/title",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": ""}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_conversation_title_unauthorized(client, test_conversation):
    """测试未认证更新会话标题"""
    response = await client.put(
        f"/api/conversations/{test_conversation.id}/title",
        json={"title": "新标题"}
    )
    
    assert response.status_code == 401


# ==================== 集成测试 ====================

@pytest.mark.asyncio
async def test_conversation_full_lifecycle(client, test_user):
    """测试会话完整生命周期"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. 创建会话
    create_response = await client.post(
        "/api/conversations/",
        headers=headers,
        json={"title": "生命周期测试会话"}
    )
    assert create_response.status_code == 200
    conv_id = create_response.json()["conversation"]["id"]
    
    # 2. 获取会话列表
    list_response = await client.get(
        "/api/conversations/",
        headers=headers
    )
    assert list_response.status_code == 200
    assert len(list_response.json()["conversations"]) == 1
    
    # 3. 获取会话详情
    detail_response = await client.get(
        f"/api/conversations/{conv_id}",
        headers=headers
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["conversation"]["title"] == "生命周期测试会话"
    
    # 4. 更新标题
    update_response = await client.put(
        f"/api/conversations/{conv_id}/title",
        headers=headers,
        json={"title": "更新后的标题"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["conversation"]["title"] == "更新后的标题"
    
    # 5. 删除会话
    delete_response = await client.delete(
        f"/api/conversations/{conv_id}",
        headers=headers
    )
    assert delete_response.status_code == 200
    
    # 6. 验证已删除
    list_response2 = await client.get(
        "/api/conversations/",
        headers=headers
    )
    assert len(list_response2.json()["conversations"]) == 0
