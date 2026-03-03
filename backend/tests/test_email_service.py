"""
iFlow 对话网页应用 - 邮箱验证码服务测试
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.database import Base
from backend.models.user import VerificationCode
from backend.services.email_service import EmailService, email_service


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
def email_svc():
    """创建邮件服务实例"""
    return EmailService()


class TestGenerateCode:
    """测试验证码生成"""

    def test_generate_code_length(self, email_svc):
        """测试验证码长度为6位"""
        code = email_svc.generate_code()
        assert len(code) == 6

    def test_generate_code_is_digit(self, email_svc):
        """测试验证码只包含数字"""
        code = email_svc.generate_code()
        assert code.isdigit()

    def test_generate_code_randomness(self, email_svc):
        """测试验证码随机性"""
        codes = [email_svc.generate_code() for _ in range(100)]
        unique_codes = set(codes)
        # 100个验证码应该有足够的随机性
        assert len(unique_codes) > 90


class TestSendEmail:
    """测试邮件发送"""

    @pytest.mark.asyncio
    async def test_send_email_success(self, email_svc):
        """测试邮件发送成功"""
        with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = None
            
            result = await email_svc.send_email(
                to_email="test@example.com",
                subject="测试主题",
                body="测试正文"
            )
            
            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_with_html(self, email_svc):
        """测试发送HTML邮件"""
        with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = None
            
            result = await email_svc.send_email(
                to_email="test@example.com",
                subject="测试主题",
                body="测试正文",
                html_body="<p>HTML正文</p>"
            )
            
            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_failure(self, email_svc):
        """测试邮件发送失败"""
        with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("SMTP连接失败")
            
            result = await email_svc.send_email(
                to_email="test@example.com",
                subject="测试主题",
                body="测试正文"
            )
            
            assert result is False


class TestSendVerificationCode:
    """测试发送验证码"""

    @pytest.mark.asyncio
    async def test_send_verification_code_success(self, email_svc, db_session):
        """测试发送验证码成功"""
        with patch.object(email_svc, 'send_email', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            success, message = await email_svc.send_verification_code(
                db=db_session,
                email="test@example.com"
            )
            
            assert success is True
            assert "已发送" in message
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_verification_code_creates_record(self, email_svc, db_session):
        """测试发送验证码创建数据库记录"""
        with patch.object(email_svc, 'send_email', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            await email_svc.send_verification_code(
                db=db_session,
                email="test@example.com"
            )
            
            # 验证数据库记录
            stmt = select(VerificationCode).where(
                VerificationCode.email == "test@example.com"
            )
            result = await db_session.execute(stmt)
            code_record = result.scalar_one_or_none()
            
            assert code_record is not None
            assert code_record.code.isdigit()
            assert len(code_record.code) == 6
            assert code_record.used is False

    @pytest.mark.asyncio
    async def test_send_verification_code_rate_limit(self, email_svc, db_session):
        """测试发送频率限制"""
        # 先发送一次
        with patch.object(email_svc, 'send_email', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await email_svc.send_verification_code(
                db=db_session,
                email="rate_test@example.com"
            )
        
        # 立即再次发送应该被限制
        success, message = await email_svc.send_verification_code(
            db=db_session,
            email="rate_test@example.com"
        )
        
        assert success is False
        assert "等待" in message

    @pytest.mark.asyncio
    async def test_send_verification_code_invalidates_old(self, email_svc, db_session):
        """测试新验证码使旧验证码失效"""
        with patch.object(email_svc, 'send_email', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # 发送第一个验证码
            await email_svc.send_verification_code(
                db=db_session,
                email="invalidate@example.com"
            )
            
            # 获取第一个验证码
            stmt = select(VerificationCode).where(
                VerificationCode.email == "invalidate@example.com"
            )
            result = await db_session.execute(stmt)
            first_code = result.scalar_one_or_none()
            
            # 模拟时间过去
            old_created_at = first_code.created_at - timedelta(seconds=70)
            first_code.created_at = old_created_at
            await db_session.commit()
            
            # 发送第二个验证码
            await email_svc.send_verification_code(
                db=db_session,
                email="invalidate@example.com"
            )
            
            # 验证第一个验证码已失效
            await db_session.refresh(first_code)
            assert first_code.used is True


class TestVerifyCode:
    """测试验证码验证"""

    @pytest.mark.asyncio
    async def test_verify_code_success(self, email_svc, db_session):
        """测试验证码验证成功"""
        # 创建一个验证码
        code = "123456"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        verification_code = VerificationCode(
            email="verify@example.com",
            code=code,
            expires_at=expires_at.replace(tzinfo=None),
            used=False
        )
        db_session.add(verification_code)
        await db_session.commit()
        
        # 验证
        success, message = await email_svc.verify_code(
            db=db_session,
            email="verify@example.com",
            code=code
        )
        
        assert success is True
        assert "成功" in message

    @pytest.mark.asyncio
    async def test_verify_code_marks_used(self, email_svc, db_session):
        """测试验证成功后标记为已使用"""
        code = "654321"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        verification_code = VerificationCode(
            email="used@example.com",
            code=code,
            expires_at=expires_at.replace(tzinfo=None),
            used=False
        )
        db_session.add(verification_code)
        await db_session.commit()
        
        # 验证
        await email_svc.verify_code(
            db=db_session,
            email="used@example.com",
            code=code
        )
        
        # 检查已标记为使用
        await db_session.refresh(verification_code)
        assert verification_code.used is True

    @pytest.mark.asyncio
    async def test_verify_code_wrong_code(self, email_svc, db_session):
        """测试错误的验证码"""
        # 创建一个验证码
        code = "111111"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        verification_code = VerificationCode(
            email="wrong@example.com",
            code=code,
            expires_at=expires_at.replace(tzinfo=None),
            used=False
        )
        db_session.add(verification_code)
        await db_session.commit()
        
        # 使用错误的验证码
        success, message = await email_svc.verify_code(
            db=db_session,
            email="wrong@example.com",
            code="999999"
        )
        
        assert success is False
        assert "错误" in message

    @pytest.mark.asyncio
    async def test_verify_code_expired(self, email_svc, db_session):
        """测试过期的验证码"""
        # 创建一个过期的验证码
        code = "222222"
        expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)  # 1分钟前过期
        verification_code = VerificationCode(
            email="expired@example.com",
            code=code,
            expires_at=expires_at.replace(tzinfo=None),
            used=False
        )
        db_session.add(verification_code)
        await db_session.commit()
        
        # 验证
        success, message = await email_svc.verify_code(
            db=db_session,
            email="expired@example.com",
            code=code
        )
        
        assert success is False
        assert "过期" in message

    @pytest.mark.asyncio
    async def test_verify_code_already_used(self, email_svc, db_session):
        """测试已使用的验证码"""
        # 创建一个已使用的验证码
        code = "333333"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        verification_code = VerificationCode(
            email="already_used@example.com",
            code=code,
            expires_at=expires_at.replace(tzinfo=None),
            used=True  # 已使用
        )
        db_session.add(verification_code)
        await db_session.commit()
        
        # 验证
        success, message = await email_svc.verify_code(
            db=db_session,
            email="already_used@example.com",
            code=code
        )
        
        assert success is False
        assert "错误" in message or "已使用" in message

    @pytest.mark.asyncio
    async def test_verify_code_nonexistent_email(self, email_svc, db_session):
        """测试不存在的邮箱"""
        success, message = await email_svc.verify_code(
            db=db_session,
            email="nonexistent@example.com",
            code="123456"
        )
        
        assert success is False
        assert "错误" in message


class TestGlobalInstance:
    """测试全局实例"""

    def test_global_instance_exists(self):
        """测试全局实例存在"""
        assert email_service is not None
        assert isinstance(email_service, EmailService)

    def test_global_instance_config(self):
        """测试全局实例配置"""
        assert email_service.smtp_server == "smtp.126.com"
        assert email_service.smtp_port == 465
        assert email_service.code_length == 6
        assert email_service.code_expire_minutes == 5
        assert email_service.rate_limit_seconds == 60