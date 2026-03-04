"""
测试会话相关的 Pydantic Schema
"""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from backend.models.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
    ConversationDetailResponse,
    ChatMessageResponse,
    ConversationTitleUpdate,
    ConversationUpdateResponse,
    ConversationDeleteResponse,
)


class TestConversationCreate:
    """测试 ConversationCreate Schema"""

    def test_create_with_defaults(self):
        """测试使用默认值创建"""
        conv = ConversationCreate()
        assert conv.title is None
        assert conv.first_message is None

    def test_create_with_title(self):
        """测试指定标题创建"""
        conv = ConversationCreate(title="我的会话")
        assert conv.title == "我的会话"
        assert conv.first_message is None

    def test_create_with_first_message(self):
        """测试指定首条消息创建"""
        conv = ConversationCreate(first_message="你好，AI")
        assert conv.title is None
        assert conv.first_message == "你好，AI"

    def test_create_with_all_fields(self):
        """测试所有字段创建"""
        conv = ConversationCreate(title="测试会话", first_message="第一条消息")
        assert conv.title == "测试会话"
        assert conv.first_message == "第一条消息"

    def test_title_max_length(self):
        """测试标题最大长度限制"""
        long_title = "a" * 256
        with pytest.raises(ValidationError) as exc_info:
            ConversationCreate(title=long_title)
        assert "at most 255 characters" in str(exc_info.value)

    def test_first_message_max_length(self):
        """测试首条消息最大长度限制"""
        long_message = "a" * 2001
        with pytest.raises(ValidationError) as exc_info:
            ConversationCreate(first_message=long_message)
        assert "at most 2000 characters" in str(exc_info.value)


class TestConversationResponse:
    """测试 ConversationResponse Schema"""

    def test_create_response(self):
        """测试创建响应模型"""
        now = datetime.now(timezone.utc)
        conv = ConversationResponse(
            id=1,
            user_id=1,
            title="测试会话",
            iflow_session_id="session-123",
            created_at=now,
            updated_at=now,
        )
        assert conv.id == 1
        assert conv.user_id == 1
        assert conv.title == "测试会话"
        assert conv.iflow_session_id == "session-123"
        assert conv.created_at == now
        assert conv.updated_at == now

    def test_create_response_without_iflow_session(self):
        """测试不包含 iflow_session_id 的响应"""
        now = datetime.now(timezone.utc)
        conv = ConversationResponse(
            id=1,
            user_id=1,
            title="测试会话",
            created_at=now,
            updated_at=now,
        )
        assert conv.iflow_session_id is None

    def test_from_attributes(self):
        """测试 from_attributes 配置（ORM 模型转换）"""
        # 模拟 ORM 对象
        class MockConversation:
            id = 1
            user_id = 1
            title = "测试会话"
            iflow_session_id = None
            created_at = datetime.now(timezone.utc)
            updated_at = datetime.now(timezone.utc)

        mock_conv = MockConversation()
        conv = ConversationResponse.model_validate(mock_conv)
        assert conv.id == 1
        assert conv.title == "测试会话"


class TestConversationListResponse:
    """测试 ConversationListResponse Schema"""

    def test_empty_list(self):
        """测试空列表"""
        response = ConversationListResponse(conversations=[], total=0)
        assert response.success is True
        assert response.conversations == []
        assert response.total == 0

    def test_list_with_conversations(self):
        """测试包含会话的列表"""
        now = datetime.now(timezone.utc)
        conv1 = ConversationResponse(
            id=1, user_id=1, title="会话1", created_at=now, updated_at=now
        )
        conv2 = ConversationResponse(
            id=2, user_id=1, title="会话2", created_at=now, updated_at=now
        )
        response = ConversationListResponse(conversations=[conv1, conv2], total=2)
        assert response.success is True
        assert len(response.conversations) == 2
        assert response.total == 2


class TestChatMessageResponse:
    """测试 ChatMessageResponse Schema"""

    def test_user_message(self):
        """测试用户消息"""
        now = datetime.now(timezone.utc)
        msg = ChatMessageResponse(id=1, role="user", content="你好", created_at=now)
        assert msg.role == "user"
        assert msg.content == "你好"

    def test_assistant_message(self):
        """测试助手消息"""
        now = datetime.now(timezone.utc)
        msg = ChatMessageResponse(id=2, role="assistant", content="你好！有什么可以帮助你的？", created_at=now)
        assert msg.role == "assistant"
        assert "可以帮助" in msg.content


class TestConversationDetailResponse:
    """测试 ConversationDetailResponse Schema"""

    def test_detail_response(self):
        """测试会话详情响应"""
        now = datetime.now(timezone.utc)
        conv = ConversationResponse(
            id=1, user_id=1, title="测试会话", created_at=now, updated_at=now
        )
        msg1 = ChatMessageResponse(id=1, role="user", content="你好", created_at=now)
        msg2 = ChatMessageResponse(id=2, role="assistant", content="你好！", created_at=now)

        response = ConversationDetailResponse(conversation=conv, messages=[msg1, msg2])
        assert response.success is True
        assert response.conversation.id == 1
        assert len(response.messages) == 2


class TestConversationTitleUpdate:
    """测试 ConversationTitleUpdate Schema"""

    def test_valid_title(self):
        """测试有效标题"""
        update = ConversationTitleUpdate(title="新标题")
        assert update.title == "新标题"

    def test_empty_title(self):
        """测试空标题"""
        with pytest.raises(ValidationError) as exc_info:
            ConversationTitleUpdate(title="")
        assert "at least 1 character" in str(exc_info.value)

    def test_title_too_long(self):
        """测试标题过长"""
        with pytest.raises(ValidationError) as exc_info:
            ConversationTitleUpdate(title="a" * 256)
        assert "at most 255 characters" in str(exc_info.value)


class TestConversationUpdateResponse:
    """测试 ConversationUpdateResponse Schema"""

    def test_update_response(self):
        """测试更新响应"""
        now = datetime.now(timezone.utc)
        conv = ConversationResponse(
            id=1, user_id=1, title="更新后的标题", created_at=now, updated_at=now
        )
        response = ConversationUpdateResponse(conversation=conv)
        assert response.success is True
        assert response.message == "标题更新成功"
        assert response.conversation.title == "更新后的标题"


class TestConversationDeleteResponse:
    """测试 ConversationDeleteResponse Schema"""

    def test_delete_response(self):
        """测试删除响应"""
        response = ConversationDeleteResponse()
        assert response.success is True
        assert response.message == "会话删除成功"
