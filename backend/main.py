"""
iFlow 对话网页应用 - FastAPI 主入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.services.scheduler import get_scheduler, start_scheduler, shutdown_scheduler
from backend.services.task_executor import execute_task_callback


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    start_scheduler()
    
    # 设置任务执行回调函数
    scheduler = get_scheduler()
    scheduler.set_task_callback(execute_task_callback)
    
    yield
    # 关闭时
    shutdown_scheduler()


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
from backend.routers import auth, websocket, chat, tasks, notifications, conversations

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(websocket.router, tags=["websocket"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
