"""
iFlow 对话网页应用 - ORM 模型定义
"""
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from backend.database import Base


def utc_now():
    """返回 UTC 时间"""
    return datetime.now(timezone.utc)


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    push_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="PushMe 推送密钥")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 关系
    chat_histories: Mapped[List["ChatHistory"]] = relationship(
        "ChatHistory", back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class Conversation(Base):
    """会话表"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="新会话")
    iflow_session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    working_directory: Mapped[str] = mapped_column(String(500), nullable=False, default="/root/.iflow-bot/workspace")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[List["ChatHistory"]] = relationship(
        "ChatHistory", back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title='{self.title}')>"


class VerificationCode(Base):
    """验证码表"""
    __tablename__ = "verification_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    def __repr__(self) -> str:
        return f"<VerificationCode(id={self.id}, email='{self.email}', code='{self.code}', used={self.used})>"

    def is_valid(self) -> bool:
        """检查验证码是否有效（未过期且未使用）"""
        if self.used:
            return False
        # SQLite 不存储时区信息，需要统一比较
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return now < self.expires_at


class ChatHistory(Base):
    """对话历史表"""
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="chat_histories")
    conversation: Mapped[Optional["Conversation"]] = relationship(
        "Conversation", back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<ChatHistory(id={self.id}, user_id={self.user_id}, conversation_id={self.conversation_id}, role='{self.role}')>"
