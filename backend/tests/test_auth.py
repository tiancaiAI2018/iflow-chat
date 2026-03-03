"""
feat-003 测试文件 - 用户认证服务（JWT + 密码哈希）

测试内容：
1. 密码哈希和验证
2. JWT Token 生成和解码
3. Token 过期验证
4. 认证依赖项
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_current_user,
    get_current_user_optional,
)
from backend.models.user import User


class TestPasswordHashing:
    """密码哈希测试"""
    
    def test_hash_password_returns_string(self):
        """测试哈希密码返回字符串"""
        password = "test_password_123"
        hashed = hash_password(password)
        
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password
    
    def test_hash_password_creates_different_hashes(self):
        """测试相同密码生成不同的哈希值（bcrypt salt）"""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # bcrypt 每次生成不同的哈希值
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """测试正确密码验证"""
        password = "correct_password"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """测试错误密码验证"""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_verify_password_empty(self):
        """测试空密码验证"""
        password = "some_password"
        hashed = hash_password(password)
        
        assert verify_password("", hashed) is False


class TestJWTToken:
    """JWT Token 测试"""
    
    def test_create_access_token_returns_string(self):
        """测试创建 Token 返回字符串"""
        data = {"sub": 1, "username": "testuser"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_access_token_with_custom_expiry(self):
        """测试自定义过期时间"""
        data = {"sub": 1}
        expires = timedelta(minutes=30)
        token = create_access_token(data, expires_delta=expires)
        
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == 1
    
    def test_decode_access_token_valid(self):
        """测试解码有效 Token"""
        data = {"sub": 123, "username": "alice", "email": "alice@example.com"}
        token = create_access_token(data)
        
        payload = decode_access_token(token)
        
        assert payload is not None
        assert payload["sub"] == 123
        assert payload["username"] == "alice"
        assert payload["email"] == "alice@example.com"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_decode_access_token_invalid(self):
        """测试解码无效 Token"""
        invalid_token = "invalid.token.string"
        
        payload = decode_access_token(invalid_token)
        
        assert payload is None
    
    def test_decode_access_token_tampered(self):
        """测试解码被篡改的 Token"""
        data = {"sub": 1}
        token = create_access_token(data)
        
        # 篡改 Token
        tampered_token = token[:-5] + "xxxxx"
        
        payload = decode_access_token(tampered_token)
        
        assert payload is None
    
    def test_decode_access_token_missing_signature(self):
        """测试解码缺少签名的 Token"""
        # 只包含 header.payload 的 Token
        incomplete_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjF9"
        
        payload = decode_access_token(incomplete_token)
        
        assert payload is None


class TestAuthDependencies:
    """认证依赖项测试"""
    
    @pytest.mark.asyncio
    async def test_get_current_user_valid(self):
        """测试获取当前用户（有效 Token）"""
        # 创建模拟用户
        mock_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # 创建有效 Token
        token = create_access_token({"sub": 1})
        
        # 模拟依赖
        mock_credentials = MagicMock()
        mock_credentials.credentials = token
        
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        # 调用依赖项
        user = await get_current_user(mock_credentials, mock_db)
        
        assert user == mock_user
        assert user.id == 1
        assert user.username == "testuser"
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """测试获取当前用户（无效 Token）"""
        from fastapi import HTTPException
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = "invalid_token"
        
        mock_db = AsyncMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials, mock_db)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_current_user_user_not_found(self):
        """测试获取当前用户（用户不存在）"""
        from fastapi import HTTPException
        
        token = create_access_token({"sub": 999})
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = token
        
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials, mock_db)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_current_user_optional_no_credentials(self):
        """测试可选认证（无凭证）"""
        user = await get_current_user_optional(None, AsyncMock())
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_get_current_user_optional_valid(self):
        """测试可选认证（有效 Token）"""
        mock_user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        token = create_access_token({"sub": 1})
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = token
        
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        user = await get_current_user_optional(mock_credentials, mock_db)
        
        assert user == mock_user
    
    @pytest.mark.asyncio
    async def test_get_current_user_optional_invalid_token(self):
        """测试可选认证（无效 Token）"""
        mock_credentials = MagicMock()
        mock_credentials.credentials = "invalid_token"
        
        mock_db = AsyncMock()
        
        user = await get_current_user_optional(mock_credentials, mock_db)
        
        assert user is None


class TestIntegration:
    """集成测试"""
    
    def test_full_auth_flow(self):
        """测试完整认证流程"""
        # 1. 用户注册时哈希密码
        plain_password = "user_password_123"
        hashed = hash_password(plain_password)
        
        # 2. 用户登录时验证密码
        assert verify_password(plain_password, hashed) is True
        
        # 3. 登录成功后创建 Token
        token = create_access_token({"sub": 1, "username": "testuser"})
        
        # 4. 后续请求解码 Token
        payload = decode_access_token(token)
        
        assert payload is not None
        assert payload["sub"] == 1
        assert payload["username"] == "testuser"
    
    def test_token_contains_expiry(self):
        """测试 Token 包含过期时间"""
        data = {"sub": 1}
        token = create_access_token(data)
        
        payload = decode_access_token(token)
        
        assert "exp" in payload
        assert "iat" in payload
        # exp 应该是未来的时间
        assert payload["exp"] > payload["iat"]
