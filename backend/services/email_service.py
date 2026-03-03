"""
iFlow 对话网页应用 - 邮箱验证码服务
"""
import random
import string
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.user import VerificationCode


class EmailService:
    """邮箱验证码服务"""

    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_use_ssl = settings.SMTP_USE_SSL
        self.code_length = settings.VERIFICATION_CODE_LENGTH
        self.code_expire_minutes = settings.VERIFICATION_CODE_EXPIRE_MINUTES
        self.rate_limit_seconds = settings.VERIFICATION_CODE_RATE_LIMIT_SECONDS

    def generate_code(self) -> str:
        """生成6位数字验证码"""
        return ''.join(random.choices(string.digits, k=self.code_length))

    async def send_email(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
        """
        发送邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body: 纯文本正文
            html_body: HTML正文（可选）
        
        Returns:
            bool: 发送是否成功
        """
        try:
            message = MIMEMultipart("alternative")
            message["From"] = self.smtp_user
            message["To"] = to_email
            message["Subject"] = subject

            # 添加纯文本正文
            message.attach(MIMEText(body, "plain", "utf-8"))

            # 添加HTML正文（如果提供）
            if html_body:
                message.attach(MIMEText(html_body, "html", "utf-8"))

            # 发送邮件
            await aiosmtplib.send(
                message,
                hostname=self.smtp_server,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                use_tls=self.smtp_use_ssl,
            )
            return True
        except Exception as e:
            print(f"发送邮件失败: {e}")
            return False

    async def send_verification_code(self, db: AsyncSession, email: str) -> Tuple[bool, str]:
        """
        发送验证码到邮箱
        
        Args:
            db: 数据库会话
            email: 目标邮箱
        
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        # 检查发送频率限制
        recent_code = await self._get_recent_code(db, email)
        if recent_code:
            time_passed = (datetime.now(timezone.utc) - recent_code.created_at.replace(tzinfo=timezone.utc)).total_seconds()
            if time_passed < self.rate_limit_seconds:
                remaining = int(self.rate_limit_seconds - time_passed)
                return False, f"请等待 {remaining} 秒后再试"

        # 使旧的验证码失效
        await self._invalidate_old_codes(db, email)

        # 生成新验证码
        code = self.generate_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.code_expire_minutes)

        # 保存到数据库
        verification_code = VerificationCode(
            email=email,
            code=code,
            expires_at=expires_at.replace(tzinfo=None),  # SQLite 不存储时区
            used=False
        )
        db.add(verification_code)
        await db.commit()

        # 发送邮件
        subject = "【iFlow Chat】邮箱验证码"
        body = f"""
您好！

您的邮箱验证码是：{code}

验证码有效期为 {self.code_expire_minutes} 分钟，请尽快使用。

如果这不是您的操作，请忽略此邮件。

iFlow Chat 团队
"""
        html_body = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #333;">邮箱验证码</h2>
    <p>您好！</p>
    <p>您的邮箱验证码是：</p>
    <div style="background-color: #f5f5f5; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 5px; margin: 20px 0;">
        {code}
    </div>
    <p style="color: #666;">验证码有效期为 {self.code_expire_minutes} 分钟，请尽快使用。</p>
    <p style="color: #999; font-size: 12px;">如果这不是您的操作，请忽略此邮件。</p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="color: #999; font-size: 12px;">iFlow Chat 团队</p>
</div>
"""

        success = await self.send_email(email, subject, body, html_body)
        if success:
            return True, "验证码已发送"
        else:
            return False, "验证码发送失败，请稍后重试"

    async def verify_code(self, db: AsyncSession, email: str, code: str) -> Tuple[bool, str]:
        """
        验证验证码
        
        Args:
            db: 数据库会话
            email: 邮箱
            code: 验证码
        
        Returns:
            Tuple[bool, str]: (是否验证成功, 消息)
        """
        # 查找验证码
        stmt = select(VerificationCode).where(
            and_(
                VerificationCode.email == email,
                VerificationCode.code == code,
                VerificationCode.used == False
            )
        ).order_by(VerificationCode.created_at.desc())
        
        result = await db.execute(stmt)
        verification_code = result.scalar_one_or_none()

        if not verification_code:
            return False, "验证码错误或已使用"

        # 检查是否过期
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if now > verification_code.expires_at:
            return False, "验证码已过期"

        # 标记为已使用
        verification_code.used = True
        await db.commit()

        return True, "验证成功"

    async def _get_recent_code(self, db: AsyncSession, email: str) -> Optional[VerificationCode]:
        """获取最近发送的验证码（用于频率限制检查）"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=self.rate_limit_seconds)
        stmt = select(VerificationCode).where(
            and_(
                VerificationCode.email == email,
                VerificationCode.created_at > cutoff_time.replace(tzinfo=None)
            )
        ).order_by(VerificationCode.created_at.desc())
        
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _invalidate_old_codes(self, db: AsyncSession, email: str) -> None:
        """使该邮箱所有未使用的旧验证码失效"""
        stmt = select(VerificationCode).where(
            and_(
                VerificationCode.email == email,
                VerificationCode.used == False
            )
        )
        result = await db.execute(stmt)
        old_codes = result.scalars().all()
        
        for old_code in old_codes:
            old_code.used = True
        
        if old_codes:
            await db.commit()


# 全局实例
email_service = EmailService()
