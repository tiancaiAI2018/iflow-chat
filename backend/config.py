"""
iFlow 对话网页应用 - 配置文件
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用配置
    APP_NAME: str = "iFlow Chat"
    DEBUG: bool = True
    
    # CORS 配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:19006",
        "http://120.53.45.173:3000",
    ]
    
    # JWT 配置
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天
    
    # 邮件服务配置 (126邮箱)
    SMTP_SERVER: str = "smtp.126.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = "wsadfg142536@126.com"
    SMTP_PASSWORD: str = "ZVes6dnvmUYV6iZM"
    SMTP_USE_SSL: bool = True
    
    # 验证码配置
    VERIFICATION_CODE_LENGTH: int = 6
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 5
    VERIFICATION_CODE_RATE_LIMIT_SECONDS: int = 60  # 1分钟1次
    
    # iFlow SDK 配置
    IFLOW_WS_URL: str = "ws://localhost:8090/acp"
    IFLOW_TIMEOUT: float = 300.0
    
    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"
    
    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_MEMORY: str = "32mb"  # Redis 最大内存限制
    REDIS_MESSAGE_TTL: int = 300  # 消息保留时间（秒），默认 5 分钟
    
    # ACP 进程管理配置
    ACP_PORT_START: int = 8091        # 端口起始
    ACP_PORT_END: int = 9000          # 端口结束（支持约 900 个并发）
    ACP_MAX_PORT_RETRIES: int = 10    # 每次分配端口时最大重试次数
    ACP_STARTUP_TIMEOUT: float = 5.0  # 进程启动超时（秒）
    
    # 数据目录
    DATA_DIR: str = "./data"
    TASKS_DIR: str = "./data/tasks"
    NOTIFICATIONS_DIR: str = "./data/notifications"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
