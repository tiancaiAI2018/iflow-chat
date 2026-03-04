# AGENTS.md - iFlow Chat 后端项目

## 项目概述

iFlow Chat 是一个基于 FastAPI 的对话网页应用后端，提供用户认证、实时对话、定时任务管理和通知功能。项目集成了 iFlow SDK 用于 AI 对话处理。

### 核心技术栈

- **Web 框架**: FastAPI
- **数据库**: SQLite (aiosqlite)
- **认证**: JWT
- **任务调度**: APScheduler
- **AI 对话**: iFlow SDK (WebSocket)
- **邮件服务**: SMTP (126邮箱)
- **测试**: pytest

---

## 项目结构

```
backend/
├── main.py                 # FastAPI 应用入口
├── config.py               # 配置文件
├── database.py             # 数据库连接模块
├── requirements.txt        # 依赖列表
├── models/                 # 数据模型
│   ├── schemas.py         # Pydantic 模型（请求/响应）
│   └── user.py            # SQLAlchemy ORM 模型
├── routers/               # API 路由
│   ├── auth.py            # 认证路由
│   ├── chat.py            # 对话路由
│   ├── tasks.py           # 定时任务路由
│   ├── notifications.py   # 通知路由
│   └── websocket.py       # WebSocket 路由
├── services/              # 业务服务
│   ├── auth.py            # 认证服务
│   ├── iflow_client.py    # iFlow SDK 封装
│   ├── scheduler.py       # 任务调度器
│   ├── task_parser.py     # 自然语言任务解析
│   ├── task_executor.py   # 任务执行器
│   ├── email_service.py   # 邮件服务
│   ├── notification_store.py  # 通知存储
│   └── websocket_manager.py   # WebSocket 管理
├── data/                  # 数据目录
│   ├── tasks/             # 定时任务 JSON 存储
│   └── notifications/    # 通知 JSON 存储
└── tests/                 # 测试目录
    ├── test_*.py          # 单元测试
    └── integration/       # 集成测试
```

---

## 关键配置 (config.py)

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `JWT_SECRET_KEY` | JWT 密钥 | `your-secret-key-change-in-production` |
| `CORS_ORIGINS` | 允许的跨域来源 | `localhost:3000`, `localhost:5173`, `120.53.45.173:3000` |
| `SMTP_*` | 126邮箱配置 | - |
| `IFLOW_WS_URL` | iFlow WebSocket 地址 | `ws://localhost:8090/acp` |
| `DATABASE_URL` | SQLite 数据库路径 | `./data/app.db` |

---

## 启动与运行

### 开发环境启动

```bash
# 进入后端目录
cd /root/.iflow-bot/workspace/mybot/backend

# 启动服务（默认端口 8000）
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 生产环境启动

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_auth.py

# 运行集成测试
pytest tests/integration/
```

---

## API 端点概览

### 认证 (`/api/auth`)

- `POST /register` - 用户注册
- `POST /login` - 用户登录
- `POST /send-code` - 发送邮箱验证码
- `POST /verify-code` - 验证码登录/注册
- `GET /me` - 获取当前用户信息

### 对话 (`/api/chat`)

- `POST /` - 发送消息（保存到数据库）
- `GET /history` - 获取聊天历史（支持分页）
- `DELETE /history` - 清空聊天历史

### 定时任务 (`/api/tasks`)

- `POST /` - 创建定时任务
- `GET /` - 获取用户任务列表
- `GET /{task_id}` - 获取单个任务
- `DELETE /{task_id}` - 删除任务
- `POST /{task_id}/toggle` - 切换任务启用状态

### 通知 (`/api/notifications`)

- `GET /` - 获取通知列表
- `POST /{id}/read` - 标记通知已读
- `POST /read-all` - 全部标记已读
- `DELETE /{id}` - 删除通知

### WebSocket (`/ws`)

- `ws://server/ws?token=xxx` - 建立 WebSocket 连接进行实时对话

---

## 核心服务说明

### iFlowClientService

`services/iflow_client.py` 封装了 iFlow SDK，提供：

- WebSocket 连接管理（自动重连）
- 流式对话处理
- 工具调用消息解析
- 定时任务意图识别（通过注入系统提示词）

### TaskScheduler

`services/scheduler.py` 使用 APScheduler 实现定时任务：

- 支持 Cron 表达式
- 任务持久化到 JSON 文件
- 服务重启后自动恢复任务
- 支持启用/禁用任务

---

## 开发规范

### 代码风格

- 使用 Pydantic v2 进行数据验证
- 使用 SQLAlchemy 2.0 ORM
- 异步优先（async/await）
- 类型注解完整

### 错误处理

- 使用统一的 `ErrorResponse` 格式
- 关键异常记录日志
- 服务层返回具体错误信息

### 测试

- 使用 pytest + pytest-asyncio
- 集成测试位于 `tests/integration/`
- 使用 httpx 作为测试客户端

---

## 注意事项

1. **JWT 密钥**: 生产环境需修改 `config.py` 中的 `JWT_SECRET_KEY`
2. **邮件配置**: 当前使用 126 邮箱，生产环境建议使用专用邮件服务
3. **iFlow SDK**: 需要确保 iFlow 服务 (`ws://localhost:8090/acp`) 可用
4. **数据库**: 首次运行自动创建 SQLite 数据库
5. **任务存储**: 定时任务和通知存储在 `data/` 目录的 JSON 文件中
