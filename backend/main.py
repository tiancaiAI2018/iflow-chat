"""
iFlow 对话网页应用 - FastAPI 主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings

app = FastAPI(
    title="iFlow Chat API",
    description="iFlow 对话网页应用后端 API",
    version="1.0.0",
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
from backend.routers import auth

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# 后续路由将在对应功能中添加
# from backend.routers import chat, tasks, notifications
# app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
# app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
# app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
