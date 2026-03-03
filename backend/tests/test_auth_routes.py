"""
iFlow 对话网页应用 - 认证路由测试

测试用户注册、登录、验证码等认证 API
"""
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.main import app
from backend.database import get_db, Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from backend.models.user import User, VerificationCode
from backend.services.auth import create_access_token, hash_password


# ==================== Fixtures ====================

@pytest.fixture(scope="function")
async def db_session():
    """创建测试数据库会话（使用内存数据库）"""
    # 创建内存数据库引擎
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    
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


# ==================== 注册接口测试 ====================

@pytest.mark.asyncio
async def test_register_success(client):
    """测试注册成功"""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "注册成功"
    assert "token" in data
    assert data["user"]["username"] == "newuser"
    assert data["user"]["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_username(client, test_user):
    """测试注册重复用户名"""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser",  # 已存在的用户名
            "email": "another@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 409
    assert "用户名已被使用" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client, test_user):
    """测试注册重复邮箱"""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "anotheruser",
            "email": "test@example.com",  # 已存在的邮箱
            "password": "password123"
        }
    )
    assert response.status_code == 409
    assert "邮箱已被注册" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_short_password(client):
    """测试注册密码过短"""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "123"  # 太短
        }
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_register_invalid_email(client):
    """测试注册无效邮箱"""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "invalid-email",  # 无效邮箱
            "password": "password123"
        }
    )
    assert response.status_code == 422  # Validation error


# ==================== 登录接口测试 ====================

@pytest.mark.asyncio
async def test_login_success(client, test_user):
    """测试登录成功"""
    response = await client.post(
        "/api/auth/login",
        json={
            "username": "testuser",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "token" in data
    assert data["user"]["username"] == "testuser"


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_user):
    """测试登录密码错误"""
    response = await client.post(
        "/api/auth/login",
        json={
            "username": "testuser",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401
    assert "用户名或密码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    """测试登录不存在的用户"""
    response = await client.post(
        "/api/auth/login",
        json={
            "username": "nonexistent",
            "password": "password123"
        }
    )
    assert response.status_code == 401
    assert "用户名或密码错误" in response.json()["detail"]


# ==================== 发送验证码测试 ====================

@pytest.mark.asyncio
async def test_send_code_success(client, db_session):
    """测试发送验证码成功"""
    # Mock 邮件发送
    with patch('backend.services.email_service.email_service.send_email', new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        
        response = await client.post(
            "/api/auth/send-code",
            json={"email": "test@example.com"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "验证码已发送"
        
        # 验证验证码已保存
        result = await db_session.execute(
            select(VerificationCode).where(VerificationCode.email == "test@example.com")
        )
        code = result.scalar_one_or_none()
        assert code is not None
        assert len(code.code) == 6


@pytest.mark.asyncio
async def test_send_code_rate_limit(client, db_session):
    """测试发送验证码频率限制"""
    # 创建一个最近发送的验证码（不带时区）
    recent_code = VerificationCode(
        email="ratelimit@example.com",
        code="123456",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        used=False,
    )
    db_session.add(recent_code)
    await db_session.commit()
    
    response = await client.post(
        "/api/auth/send-code",
        json={"email": "ratelimit@example.com"}
    )
    
    assert response.status_code == 429
    assert "请等待" in response.json()["detail"]


# ==================== 验证码登录测试 ====================

@pytest.mark.asyncio
async def test_verify_code_existing_user(client, db_session, test_user):
    """测试验证码登录已存在用户"""
    # 创建验证码（不带时区）
    code = VerificationCode(
        email="test@example.com",
        code="654321",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        used=False,
    )
    db_session.add(code)
    await db_session.commit()
    
    response = await client.post(
        "/api/auth/verify-code",
        json={
            "email": "test@example.com",
            "code": "654321"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["is_new_user"] is False
    assert "token" in data
    assert data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_verify_code_new_user(client, db_session):
    """测试验证码注册新用户"""
    # 创建验证码（不带时区）
    code = VerificationCode(
        email="newuser@example.com",
        code="111111",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        used=False,
    )
    db_session.add(code)
    await db_session.commit()
    
    response = await client.post(
        "/api/auth/verify-code",
        json={
            "email": "newuser@example.com",
            "code": "111111"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["is_new_user"] is True
    assert "token" in data
    assert data["user"]["email"] == "newuser@example.com"
    # 用户名应该是邮箱前缀
    assert "newuser" in data["user"]["username"]


@pytest.mark.asyncio
async def test_verify_code_invalid(client):
    """测试验证码无效"""
    response = await client.post(
        "/api/auth/verify-code",
        json={
            "email": "test@example.com",
            "code": "000000"  # 不存在的验证码
        }
    )
    
    assert response.status_code == 400
    assert "验证码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_verify_code_expired(client, db_session):
    """测试验证码过期"""
    # 创建过期验证码（不带时区）
    expired_code = VerificationCode(
        email="expired@example.com",
        code="999999",
        expires_at=datetime.utcnow() - timedelta(minutes=1),  # 已过期
        used=False,
    )
    db_session.add(expired_code)
    await db_session.commit()
    
    response = await client.post(
        "/api/auth/verify-code",
        json={
            "email": "expired@example.com",
            "code": "999999"
        }
    )
    
    assert response.status_code == 400
    assert "已过期" in response.json()["detail"]


# ==================== 获取当前用户测试 ====================

@pytest.mark.asyncio
async def test_get_me_success(client, test_user):
    """测试获取当前用户信息成功"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user"]["username"] == "testuser"
    assert data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_me_no_token(client):
    """测试获取当前用户无 Token"""
    response = await client.get("/api/auth/me")
    
    assert response.status_code == 401  # Unauthorized (HTTPBearer 返回 401)


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    """测试获取当前用户无效 Token"""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_nonexistent_user(client):
    """测试获取当前用户不存在"""
    # 使用不存在的用户 ID 创建 Token
    token = create_access_token({"sub": 99999, "username": "nonexistent"})
    
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 401


# ==================== 集成测试 ====================

@pytest.mark.asyncio
async def test_register_then_login(client):
    """测试注册后登录流程"""
    # 注册
    register_response = await client.post(
        "/api/auth/register",
        json={
            "username": "integration_user",
            "email": "integration@example.com",
            "password": "password123"
        }
    )
    assert register_response.status_code == 200
    
    # 登录
    login_response = await client.post(
        "/api/auth/login",
        json={
            "username": "integration_user",
            "password": "password123"
        }
    )
    assert login_response.status_code == 200
    
    # 使用 Token 获取用户信息
    token = login_response.json()["token"]
    me_response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["user"]["username"] == "integration_user"
