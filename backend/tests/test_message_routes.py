"""
待消费消息 API 路由测试

测试内容：
- GET /api/messages/pending - 获取待消费消息
- POST /api/messages/consume - 消费消息
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from backend.models.user import User


@pytest.fixture
def mock_user():
    """模拟用户"""
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    return user


@pytest.fixture
def mock_message_buffer():
    """模拟 MessageBuffer"""
    buffer = AsyncMock()
    buffer.get_pending = AsyncMock(return_value=None)
    buffer.consume = AsyncMock(return_value=None)
    return buffer


@pytest.fixture
def app_with_deps(mock_user, mock_message_buffer):
    """创建带 mock 依赖的应用"""
    from fastapi import FastAPI
    from backend.routers.messages import router
    from backend.models.user import User

    app = FastAPI()
    app.include_router(router, prefix="/api/messages")

    # 覆盖依赖
    async def override_get_current_user():
        return mock_user

    def override_get_message_buffer():
        return mock_message_buffer

    from backend.routers.messages import get_message_buffer_dep
    from backend.services.auth import get_current_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_message_buffer_dep] = override_get_message_buffer

    return app


class TestGetPendingMessages:
    """测试 GET /api/messages/pending"""

    @pytest.mark.asyncio
    async def test_get_pending_messages_empty(self, mock_user, mock_message_buffer, app_with_deps):
        """测试无待消费消息"""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/messages/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["messages"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_get_pending_messages_with_data(self, mock_user, mock_message_buffer, app_with_deps):
        """测试有待消费消息"""
        # 模拟 Redis Stream 返回格式
        mock_message_buffer.get_pending.return_value = [
            ("user:1:messages", [
                ("1234567890123-0", {"data": json.dumps({
                    "type": "stream",
                    "content": "Hello",
                    "is_delta": True,
                    "conversation_id": 1
                })}),
                ("1234567890123-1", {"data": json.dumps({
                    "type": "complete",
                    "content": "Hello World",
                    "conversation_id": 1
                })}),
            ])
        ]

        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/messages/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 2
        assert len(data["messages"]) == 2

        # 验证消息格式
        msg1 = data["messages"][0]
        assert msg1["entry_id"] == "1234567890123-0"
        assert msg1["type"] == "stream"
        assert msg1["content"] == "Hello"
        assert msg1["is_delta"] is True
        assert msg1["conversation_id"] == 1

        msg2 = data["messages"][1]
        assert msg2["entry_id"] == "1234567890123-1"
        assert msg2["type"] == "complete"

    @pytest.mark.asyncio
    async def test_get_pending_messages_count_parameter(self, mock_user, mock_message_buffer, app_with_deps):
        """测试 count 参数"""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/messages/pending?count=20")

        # 验证 count 参数传递正确
        mock_message_buffer.get_pending.assert_called_once()
        call_kwargs = mock_message_buffer.get_pending.call_args[1]
        assert call_kwargs["count"] == 20

    @pytest.mark.asyncio
    async def test_get_pending_messages_invalid_json(self, mock_user, mock_message_buffer, app_with_deps):
        """测试无效 JSON 数据"""
        mock_message_buffer.get_pending.return_value = [
            ("user:1:messages", [
                ("1234567890123-0", {"data": "invalid json"}),
            ])
        ]

        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/messages/pending")

        # 无效 JSON 应被跳过，返回空列表
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_get_pending_messages_error_handling(self, mock_user, mock_message_buffer, app_with_deps):
        """测试错误处理"""
        mock_message_buffer.get_pending.side_effect = Exception("Redis error")

        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/messages/pending")

        # 错误应被捕获并返回空列表
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert "失败" in data["message"]


class TestConsumeMessages:
    """测试 POST /api/messages/consume"""

    @pytest.mark.asyncio
    async def test_consume_messages_empty(self, mock_user, mock_message_buffer, app_with_deps):
        """测试无消息可消费"""
        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test"
        ) as client:
            response = await client.post("/api/messages/consume")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["messages"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_consume_messages_with_data(self, mock_user, mock_message_buffer, app_with_deps):
        """测试消费消息"""
        mock_message_buffer.consume.return_value = [
            ("user:1:messages", [
                ("1234567890123-0", {"data": json.dumps({
                    "type": "stream",
                    "content": "Consumed",
                    "is_delta": True,
                })}),
            ])
        ]

        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test"
        ) as client:
            response = await client.post("/api/messages/consume?count=5")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["messages"][0]["content"] == "Consumed"

        # 验证 consume 被正确调用
        mock_message_buffer.consume.assert_called_once()
        call_kwargs = mock_message_buffer.consume.call_args[1]
        assert call_kwargs["count"] == 5


class TestPendingMessageItemFormat:
    """测试消息项格式"""

    @pytest.mark.asyncio
    async def test_message_with_all_fields(self, mock_user, mock_message_buffer, app_with_deps):
        """测试包含所有字段的消息"""
        mock_message_buffer.get_pending.return_value = [
            ("user:1:messages", [
                ("1234567890123-0", {"data": json.dumps({
                    "type": "stream",
                    "content": "Test content with unicode 你好世界",
                    "is_delta": True,
                    "conversation_id": 123,
                    "created_at": "2026-03-07T10:00:00Z"
                })}),
            ])
        ]

        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/messages/pending")

        assert response.status_code == 200
        data = response.json()
        msg = data["messages"][0]

        assert msg["entry_id"] == "1234567890123-0"
        assert msg["type"] == "stream"
        assert msg["content"] == "Test content with unicode 你好世界"
        assert msg["is_delta"] is True
        assert msg["conversation_id"] == 123
        assert msg["created_at"] == "2026-03-07T10:00:00Z"

    @pytest.mark.asyncio
    async def test_message_with_minimal_fields(self, mock_user, mock_message_buffer, app_with_deps):
        """测试仅包含必要字段的消息"""
        mock_message_buffer.get_pending.return_value = [
            ("user:1:messages", [
                ("1234567890123-0", {"data": json.dumps({
                    "type": "complete",
                    "content": "Minimal",
                })}),
            ])
        ]

        async with AsyncClient(
            transport=ASGITransport(app=app_with_deps),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/messages/pending")

        assert response.status_code == 200
        data = response.json()
        msg = data["messages"][0]

        assert msg["type"] == "complete"
        assert msg["content"] == "Minimal"
        assert msg["is_delta"] is None
        assert msg["conversation_id"] is None
