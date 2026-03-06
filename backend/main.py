"""
iFlow 对话网页应用 - FastAPI 主入口
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.services.scheduler import get_scheduler, start_scheduler, shutdown_scheduler
from backend.services.task_executor import execute_task_callback

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局资源（在 lifespan 中初始化）
_message_buffer: Optional['MessageBuffer'] = None
_redis_output_handler: Optional['RedisOutputHandler'] = None
_db_output_handler: Optional['DBOutputHandler'] = None
_iflow_processor: Optional['IFlowProcessor'] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global _message_buffer, _redis_output_handler, _db_output_handler, _iflow_processor

    logger.info("Starting application...")

    # ============ 启动时初始化 ============

    # 1. 启动调度器
    start_scheduler()
    scheduler = get_scheduler()
    scheduler.set_task_callback(execute_task_callback)
    logger.info("Scheduler started")

    # 2. 初始化 Redis 连接（MessageBuffer）
    from backend.services.message_buffer import MessageBuffer
    _message_buffer = MessageBuffer(
        redis_url=settings.REDIS_URL,
        ttl=settings.REDIS_MESSAGE_TTL
    )
    # 测试 Redis 连接
    try:
        await _message_buffer.redis.ping()
        logger.info(f"Redis connected: {settings.REDIS_URL}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

    # 3. 初始化输入处理器（WebSocketInputHandler 不需要全局实例，在 WebSocket 连接时创建）
    # 注意：WebSocketInputHandler 是无状态的，每次使用创建新实例即可
    logger.info("WebSocketInputHandler ready (created per connection)")

    # 4. 初始化输出处理器
    from backend.services.output_handlers import RedisOutputHandler, DBOutputHandler

    # Redis 输出处理器（用于断线重连恢复）
    _redis_output_handler = RedisOutputHandler(buffer=_message_buffer)
    logger.info("RedisOutputHandler initialized")

    # 数据库输出处理器（用于持久化 AI 响应）
    from backend.database import async_session_maker
    _db_output_handler = DBOutputHandler(db_session_factory=async_session_maker)
    logger.info("DBOutputHandler initialized")

    # 5. 初始化 IFlow 业务逻辑处理器
    from backend.services.iflow_processor import get_iflow_processor
    _iflow_processor = get_iflow_processor()
    logger.info("IFlowProcessor initialized")

    logger.info("Application started successfully")

    yield

    # ============ 关闭时清理 ============
    logger.info("Shutting down application...")

    # 1. 断开 IFlow 处理器
    if _iflow_processor:
        try:
            await _iflow_processor.close()
            logger.info("IFlowProcessor closed")
        except Exception as e:
            logger.warning(f"Error closing IFlowProcessor: {e}")

    # 2. 断开输出处理器
    if _redis_output_handler:
        try:
            _redis_output_handler.disconnect()
            logger.info("RedisOutputHandler disconnected")
        except Exception as e:
            logger.warning(f"Error disconnecting RedisOutputHandler: {e}")

    if _db_output_handler:
        try:
            await _db_output_handler.close()
            logger.info("DBOutputHandler closed")
        except Exception as e:
            logger.warning(f"Error closing DBOutputHandler: {e}")

    # 3. 关闭 Redis 连接
    if _message_buffer:
        try:
            await _message_buffer.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")

    # 4. 关闭调度器
    shutdown_scheduler()
    logger.info("Scheduler shutdown")

    logger.info("Application shutdown complete")


app = FastAPI(
    title="iFlow Chat API",
    description="iFlow 对话网页应用后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """健康检查接口"""
    return {"status": "ok", "message": "iFlow Chat API is running"}


@app.get("/health")
async def health():
    """健康检查接口"""
    return {"status": "healthy"}


# 导入并注册路由
from backend.routers import auth, websocket, chat, tasks, notifications, conversations, directories

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(websocket.router, tags=["websocket"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(directories.router, prefix="/api/directories", tags=["directories"])


# ============ 获取全局资源的辅助函数 ============

def get_message_buffer() -> 'MessageBuffer':
    """获取全局 MessageBuffer 实例"""
    if _message_buffer is None:
        raise RuntimeError("MessageBuffer not initialized. Application may not have started.")
    return _message_buffer


def get_redis_output_handler() -> 'RedisOutputHandler':
    """获取全局 RedisOutputHandler 实例"""
    if _redis_output_handler is None:
        raise RuntimeError("RedisOutputHandler not initialized. Application may not have started.")
    return _redis_output_handler