"""
iFlow 对话网页应用 - 用户认证流程集成测试

测试完整的用户认证流程：
- 用户名密码注册流程
- 用户名密码登录流程
- 邮箱验证码发送
- 验证码登录/注册流程
- Token 验证
"""
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.main import app
from backend.database import get_db, Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from backend.models.user import User, VerificationCode
from backend.services.auth import create_access_token, hash_password, decode_access_token


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


# ==================== 用户名密码注册流程测试 ====================

@pytest.mark.asyncio
class TestUsernamePasswordRegisterFlow:
    """用户名密码注册流程集成测试"""
    
    async def test_register_flow_success(self, client, db_session):
        """测试完整的注册流程：注册 -> 验证数据库 -> 登录"""
        # Step 1: 注册新用户
        register_response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "SecurePass123"
            }
        )
        
        # 验证注册响应
        assert register_response.status_code == 200
        register_data = register_response.json()
        assert register_data["success"] is True
        assert register_data["message"] == "注册成功"
        assert "token" in register_data
        assert register_data["user"]["username"] == "newuser"
        assert register_data["user"]["email"] == "newuser@example.com"
        
        # Step 2: 验证数据库中用户已创建
        result = await db_session.execute(
            select(User).where(User.username == "newuser")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email == "newuser@example.com"
        assert user.password_hash != "SecurePass123"  # 密码应该被哈希
        
        # Step 3: 验证 Token 有效
        token = register_data["token"]
        token_data = decode_access_token(token)
        assert token_data is not None
        assert token_data["sub"] == user.id
        
        # Step 4: 使用 Token 获取用户信息
        me_response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        assert me_response.json()["user"]["username"] == "newuser"
    
    async def test_register_duplicate_username_flow(self, client, db_session):
        """测试注册重复用户名的完整流程"""
        # Step 1: 创建第一个用户
        user1 = User(
            username="existinguser",
            email="user1@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(user1)
        await db_session.commit()
        
        # Step 2: 尝试用相同用户名注册
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "existinguser",  # 已存在
                "email": "different@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 409
        assert "用户名已被使用" in response.json()["detail"]
    
    async def test_register_duplicate_email_flow(self, client, db_session):
        """测试注册重复邮箱的完整流程"""
        # Step 1: 创建第一个用户
        user1 = User(
            username="user1",
            email="same@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(user1)
        await db_session.commit()
        
        # Step 2: 尝试用相同邮箱注册
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "differentuser",
                "email": "same@example.com",  # 已存在
                "password": "password123"
            }
        )
        
        assert response.status_code == 409
        assert "邮箱已被注册" in response.json()["detail"]


# ==================== 用户名密码登录流程测试 ====================

@pytest.mark.asyncio
class TestUsernamePasswordLoginFlow:
    """用户名密码登录流程集成测试"""
    
    async def test_login_flow_success(self, client, db_session):
        """测试完整的登录流程：创建用户 -> 登录 -> 验证Token"""
        # Step 1: 创建测试用户
        user = User(
            username="loginuser",
            email="login@example.com",
            password_hash=hash_password("correctpassword"),
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Step 2: 登录
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "loginuser",
                "password": "correctpassword"
            }
        )
        
        # 验证登录响应
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data["success"] is True
        assert "token" in login_data
        assert login_data["user"]["username"] == "loginuser"
        
        # Step 3: 验证 Token 有效
        token = login_data["token"]
        token_data = decode_access_token(token)
        assert token_data is not None
        assert token_data["sub"] == user.id
        
        # Step 4: 验证 last_login 已更新
        await db_session.refresh(user)
        assert user.last_login is not None
    
    async def test_login_wrong_password_flow(self, client, db_session):
        """测试登录密码错误的流程"""
        # Step 1: 创建测试用户
        user = User(
            username="wrongpassuser",
            email="wrongpass@example.com",
            password_hash=hash_password("correctpassword"),
        )
        db_session.add(user)
        await db_session.commit()
        
        # Step 2: 用错误密码登录
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "wrongpassuser",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        assert "用户名或密码错误" in response.json()["detail"]
    
    async def test_login_nonexistent_user_flow(self, client):
        """测试登录不存在用户的流程"""
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "nonexistent",
                "password": "anypassword"
            }
        )
        
        assert response.status_code == 401
        assert "用户名或密码错误" in response.json()["detail"]


# ==================== 邮箱验证码发送测试 ====================

@pytest.mark.asyncio
class TestEmailVerificationCodeFlow:
    """邮箱验证码发送流程集成测试"""
    
    async def test_send_code_flow_success(self, client, db_session):
        """测试完整的验证码发送流程"""
        # Mock 邮件发送
        with patch('backend.services.email_service.email_service.send_email', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # Step 1: 发送验证码
            response = await client.post(
                "/api/auth/send-code",
                json={"email": "test@example.com"}
            )
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "验证码已发送"
            
            # Step 2: 验证验证码已保存到数据库
            result = await db_session.execute(
                select(VerificationCode)
                .where(VerificationCode.email == "test@example.com")
                .order_by(VerificationCode.created_at.desc())
            )
            code = result.scalar_one_or_none()
            assert code is not None
            assert len(code.code) == 6
            assert code.used is False
            assert code.expires_at > datetime.utcnow()
            
            # Step 3: 验证邮件发送被调用
            mock_send.assert_called_once()
    
    async def test_send_code_rate_limit_flow(self, client, db_session):
        """测试验证码发送频率限制流程"""
        # Step 1: 创建一个最近发送的验证码
        recent_code = VerificationCode(
            email="ratelimit@example.com",
            code="123456",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            used=False,
        )
        db_session.add(recent_code)
        await db_session.commit()
        
        # Step 2: 尝试再次发送
        response = await client.post(
            "/api/auth/send-code",
            json={"email": "ratelimit@example.com"}
        )
        
        assert response.status_code == 429
        assert "请等待" in response.json()["detail"]
    
    async def test_send_code_multiple_times_different_emails(self, client, db_session):
        """测试不同邮箱可以同时发送验证码"""
        with patch('backend.services.email_service.email_service.send_email', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # 发送第一个邮箱
            response1 = await client.post(
                "/api/auth/send-code",
                json={"email": "email1@example.com"}
            )
            assert response1.status_code == 200
            
            # 发送第二个邮箱
            response2 = await client.post(
                "/api/auth/send-code",
                json={"email": "email2@example.com"}
            )
            assert response2.status_code == 200
            
            # 验证两个验证码都已保存
            result = await db_session.execute(
                select(VerificationCode)
                .where(VerificationCode.email.in_(["email1@example.com", "email2@example.com"]))
            )
            codes = result.scalars().all()
            assert len(codes) == 2


# ==================== 验证码登录/注册流程测试 ====================

@pytest.mark.asyncio
class TestVerificationCodeLoginFlow:
    """验证码登录/注册流程集成测试"""
    
    async def test_verify_code_login_existing_user_flow(self, client, db_session):
        """测试验证码登录已存在用户的完整流程"""
        # Step 1: 创建已存在用户
        user = User(
            username="existinguser",
            email="existing@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(user)
        await db_session.commit()
        
        # Step 2: 创建验证码
        code = VerificationCode(
            email="existing@example.com",
            code="123456",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            used=False,
        )
        db_session.add(code)
        await db_session.commit()
        
        # Step 3: 验证码登录
        response = await client.post(
            "/api/auth/verify-code",
            json={
                "email": "existing@example.com",
                "code": "123456"
            }
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_new_user"] is False
        assert "token" in data
        assert data["user"]["email"] == "existing@example.com"
        assert data["user"]["username"] == "existinguser"
        
        # Step 4: 验证验证码已标记为已使用
        await db_session.refresh(code)
        assert code.used is True
        
        # Step 5: 验证同一验证码不能再次使用
        response2 = await client.post(
            "/api/auth/verify-code",
            json={
                "email": "existing@example.com",
                "code": "123456"
            }
        )
        assert response2.status_code == 400
    
    async def test_verify_code_register_new_user_flow(self, client, db_session):
        """测试验证码注册新用户的完整流程"""
        # Step 1: 创建验证码
        code = VerificationCode(
            email="newuser@example.com",
            code="654321",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            used=False,
        )
        db_session.add(code)
        await db_session.commit()
        
        # Step 2: 验证码登录（新用户自动注册）
        response = await client.post(
            "/api/auth/verify-code",
            json={
                "email": "newuser@example.com",
                "code": "654321"
            }
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_new_user"] is True
        assert "token" in data
        assert data["user"]["email"] == "newuser@example.com"
        
        # Step 3: 验证用户已创建
        result = await db_session.execute(
            select(User).where(User.email == "newuser@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert "newuser" in user.username
        
        # Step 4: 验证验证码已标记为已使用
        await db_session.refresh(code)
        assert code.used is True
    
    async def test_verify_code_expired_flow(self, client, db_session):
        """测试使用过期验证码的流程"""
        # Step 1: 创建过期验证码
        expired_code = VerificationCode(
            email="expired@example.com",
            code="999999",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
            used=False,
        )
        db_session.add(expired_code)
        await db_session.commit()
        
        # Step 2: 尝试使用过期验证码
        response = await client.post(
            "/api/auth/verify-code",
            json={
                "email": "expired@example.com",
                "code": "999999"
            }
        )
        
        assert response.status_code == 400
        assert "已过期" in response.json()["detail"]
    
    async def test_verify_code_invalid_flow(self, client):
        """测试使用无效验证码的流程"""
        response = await client.post(
            "/api/auth/verify-code",
            json={
                "email": "test@example.com",
                "code": "000000"
            }
        )
        
        assert response.status_code == 400
        assert "验证码错误" in response.json()["detail"]


# ==================== Token 验证测试 ====================

@pytest.mark.asyncio
class TestTokenValidationFlow:
    """Token 验证流程集成测试"""
    
    async def test_token_validation_success_flow(self, client, db_session):
        """测试 Token 验证成功流程"""
        # Step 1: 创建用户
        user = User(
            username="tokenuser",
            email="token@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Step 2: 生成 Token
        token = create_access_token({"sub": user.id, "username": user.username})
        
        # Step 3: 使用 Token 获取用户信息
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user"]["username"] == "tokenuser"
        assert data["user"]["email"] == "token@example.com"
    
    async def test_token_validation_no_token_flow(self, client):
        """测试无 Token 访问受保护接口"""
        response = await client.get("/api/auth/me")
        
        assert response.status_code == 401
    
    async def test_token_validation_invalid_token_flow(self, client):
        """测试无效 Token 访问受保护接口"""
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        
        assert response.status_code == 401
    
    async def test_token_validation_nonexistent_user_flow(self, client):
        """测试 Token 对应不存在的用户"""
        # 生成不存在用户的 Token
        token = create_access_token({"sub": 99999, "username": "nonexistent"})
        
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 401


# ==================== 完整认证流程集成测试 ====================

@pytest.mark.asyncio
class TestFullAuthenticationFlow:
    """完整认证流程集成测试"""
    
    async def test_full_username_password_flow(self, client, db_session):
        """测试完整的用户名密码认证流程：注册 -> 登录 -> 访问受保护资源"""
        # Step 1: 注册新用户
        register_response = await client.post(
            "/api/auth/register",
            json={
                "username": "fullflowuser",
                "email": "fullflow@example.com",
                "password": "SecurePass123"
            }
        )
        assert register_response.status_code == 200
        register_token = register_response.json()["token"]
        
        # Step 2: 使用注册返回的 Token 访问受保护资源
        me_response1 = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {register_token}"}
        )
        assert me_response1.status_code == 200
        
        # Step 3: 登录获取新 Token
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "fullflowuser",
                "password": "SecurePass123"
            }
        )
        assert login_response.status_code == 200
        login_token = login_response.json()["token"]
        
        # Step 4: 使用登录 Token 访问受保护资源
        me_response2 = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {login_token}"}
        )
        assert me_response2.status_code == 200
        assert me_response2.json()["user"]["username"] == "fullflowuser"
    
    async def test_full_email_verification_flow(self, client, db_session):
        """测试完整的邮箱验证码认证流程：发送验证码 -> 验证登录 -> 访问受保护资源"""
        with patch('backend.services.email_service.email_service.send_email', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # Step 1: 发送验证码
            send_response = await client.post(
                "/api/auth/send-code",
                json={"email": "emailflow@example.com"}
            )
            assert send_response.status_code == 200
            
            # Step 2: 获取验证码
            result = await db_session.execute(
                select(VerificationCode)
                .where(VerificationCode.email == "emailflow@example.com")
                .order_by(VerificationCode.created_at.desc())
            )
            code = result.scalar_one()
            
            # Step 3: 验证码登录（新用户自动注册）
            verify_response = await client.post(
                "/api/auth/verify-code",
                json={
                    "email": "emailflow@example.com",
                    "code": code.code
                }
            )
            assert verify_response.status_code == 200
            verify_data = verify_response.json()
            assert verify_data["is_new_user"] is True
            
            token = verify_data["token"]
            
            # Step 4: 使用 Token 访问受保护资源
            me_response = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert me_response.status_code == 200
            assert me_response.json()["user"]["email"] == "emailflow@example.com"
    
    async def test_full_mixed_auth_flow(self, client, db_session):
        """测试混合认证流程：用户名密码注册后用邮箱验证码登录"""
        # Step 1: 用户名密码注册
        register_response = await client.post(
            "/api/auth/register",
            json={
                "username": "mixeduser",
                "email": "mixed@example.com",
                "password": "password123"
            }
        )
        assert register_response.status_code == 200
        
        # Step 2: 发送验证码到相同邮箱
        with patch('backend.services.email_service.email_service.send_email', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            send_response = await client.post(
                "/api/auth/send-code",
                json={"email": "mixed@example.com"}
            )
            assert send_response.status_code == 200
            
            # Step 3: 获取验证码
            result = await db_session.execute(
                select(VerificationCode)
                .where(VerificationCode.email == "mixed@example.com")
                .order_by(VerificationCode.created_at.desc())
            )
            code = result.scalar_one()
            
            # Step 4: 用验证码登录（应该是已存在用户）
            verify_response = await client.post(
                "/api/auth/verify-code",
                json={
                    "email": "mixed@example.com",
                    "code": code.code
                }
            )
            assert verify_response.status_code == 200
            verify_data = verify_response.json()
            assert verify_data["is_new_user"] is False  # 已存在用户
            assert verify_data["user"]["username"] == "mixeduser"
