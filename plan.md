# iFlow 对话网页应用 - 完整实施计划

## 项目概述

构建一个可以与 iFlow 对话的网页应用，支持基础对话、工具调用展示、定时任务（自然语言创建）、通知系统，并具备用户认证功能。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + CSS (移动端适配) |
| 后端 | Python 3.11 + FastAPI + APScheduler + SQLite |
| 实时通信 | WebSocket |
| 认证 | JWT Token + 邮箱验证码 |
| AI 集成 | iflow-cli-sdk |
| 邮件服务 | SMTP (126邮箱) |

---

## 项目结构

```
mybot/
├── backend/                        # Python 后端
│   ├── main.py                     # FastAPI 应用入口
│   ├── config.py                   # 配置文件
│   ├── database.py                 # SQLite 数据库连接
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py              # Pydantic 请求/响应模型
│   │   └── user.py                 # 用户 ORM 模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── iflow_client.py         # iFlow SDK 封装
│   │   ├── scheduler.py            # 定时任务调度器
│   │   ├── notification_store.py   # 通知存储管理
│   │   ├── email_service.py        # 邮箱验证码服务
│   │   └── auth.py                 # JWT 认证服务
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py                 # 认证相关路由
│   │   ├── chat.py                 # 对话相关路由
│   │   ├── tasks.py                # 定时任务路由
│   │   └── notifications.py        # 通知路由
│   ├── data/
│   │   ├── app.db                  # SQLite 数据库文件
│   │   ├── tasks/                  # 用户定时任务 JSON
│   │   │   └── {user_id}.json
│   │   └── notifications/          # 用户通知 JSON
│   │       └── {user_id}.json
│   └── requirements.txt
│
├── frontend/                       # React 前端
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── index.tsx
│   │   ├── App.tsx
│   │   ├── App.css
│   │   ├── components/
│   │   │   ├── Auth/
│   │   │   │   ├── Login.tsx       # 登录页面
│   │   │   │   ├── Register.tsx    # 注册页面
│   │   │   │   └── Auth.css
│   │   │   ├── Chat/
│   │   │   │   ├── Chat.tsx        # 对话主界面
│   │   │   │   ├── Message.tsx     # 单条消息组件
│   │   │   │   ├── MessageInput.tsx # 消息输入框
│   │   │   │   └── Chat.css
│   │   │   ├── ToolCall/
│   │   │   │   ├── ToolCall.tsx    # 工具调用展示卡片
│   │   │   │   └── ToolCall.css
│   │   │   ├── Notification/
│   │   │   │   ├── NotificationBar.tsx # 通知栏
│   │   │   │   ├── NotificationItem.tsx # 单条通知
│   │   │   │   └── Notification.css
│   │   │   ├── TaskManager/
│   │   │   │   ├── TaskList.tsx    # 任务列表
│   │   │   │   ├── TaskCreator.tsx # 任务创建(自然语言)
│   │   │   │   └── TaskManager.css
│   │   │   └── Layout/
│   │   │       ├── Header.tsx      # 顶部导航
│   │   │       └── Layout.css
│   │   ├── hooks/
│   │   │   ├── useAuth.ts          # 认证状态管理
│   │   │   ├── useWebSocket.ts     # WebSocket 连接
│   │   │   └── useNotifications.ts # 通知管理
│   │   ├── services/
│   │   │   └── api.ts              # API 请求封装
│   │   └── types/
│   │       └── index.ts            # TypeScript 类型定义
│   ├── package.json
│   └── tsconfig.json
│
└── plan.md                         # 本文档
```

---

## API 设计

### 认证模块 `/api/auth`

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/register` | 用户名密码注册 | 否 |
| POST | `/login` | 用户名密码登录 | 否 |
| POST | `/send-code` | 发送邮箱验证码 | 否 |
| POST | `/verify-code` | 验证码登录/注册 | 否 |
| GET | `/me` | 获取当前用户信息 | 是 |

**请求/响应示例:**

```json
// POST /api/auth/register
{
  "username": "alice",
  "password": "password123",
  "email": "alice@example.com"
}
// Response
{
  "success": true,
  "message": "注册成功",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}

// POST /api/auth/login
{
  "username": "alice",
  "password": "password123"
}
// Response
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com"
  }
}

// POST /api/auth/send-code
{
  "email": "alice@example.com"
}
// Response
{
  "success": true,
  "message": "验证码已发送"
}

// POST /api/auth/verify-code
{
  "email": "alice@example.com",
  "code": "123456"
}
// Response
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": { ... },
  "is_new_user": false
}
```

### 对话模块 `/api/chat`

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/` | 发送消息 | 是 |
| GET | `/history` | 获取历史记录 | 是 |
| WS | `/ws/{user_id}` | WebSocket 连接 | 是 |

**WebSocket 消息格式:**

```typescript
// 客户端 -> 服务器
{
  "type": "chat",
  "content": "你好，请帮我分析一下今天的天气"
}

// 服务器 -> 客户端 (流式文本)
{
  "type": "assistant_message",
  "content": "今天天气...",
  "is_delta": true,
  "is_finished": false
}

// 服务器 -> 客户端 (工具调用)
{
  "type": "tool_call",
  "tool_name": "get_weather",
  "arguments": { "city": "北京" },
  "status": "running" | "success" | "error",
  "result": { ... }
}

// 服务器 -> 客户端 (通知推送)
{
  "type": "notification",
  "notification": {
    "id": "notif_001",
    "content": "定时任务执行结果...",
    "created_at": "2026-03-03T09:00:00"
  }
}
```

### 定时任务模块 `/api/tasks`

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | `/` | 获取用户任务列表 | 是 |
| POST | `/` | 创建任务(自然语言) | 是 |
| DELETE | `/{task_id}` | 删除任务 | 是 |
| PUT | `/{task_id}/toggle` | 启用/禁用任务 | 是 |

**请求/响应示例:**

```json
// POST /api/tasks
{
  "description": "每天早上9点提醒我查看股票"
}
// Response
{
  "success": true,
  "task": {
    "id": "task_001",
    "content": "查看股票",
    "cron": "0 9 * * *",
    "natural_language": "每天早上9点提醒我查看股票",
    "enabled": true,
    "created_at": "2026-03-03T10:00:00"
  }
}

// GET /api/tasks
// Response
{
  "tasks": [
    {
      "id": "task_001",
      "content": "查看股票",
      "cron": "0 9 * * *",
      "natural_language": "每天早上9点提醒我查看股票",
      "enabled": true,
      "last_run": "2026-03-03T09:00:00",
      "next_run": "2026-03-04T09:00:00"
    }
  ]
}
```

### 通知模块 `/api/notifications`

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | `/` | 获取通知列表 | 是 |
| PUT | `/{id}/read` | 标记已读 | 是 |
| DELETE | `/{id}` | 删除通知 | 是 |

**请求/响应示例:**

```json
// GET /api/notifications?unread_only=true
// Response
{
  "notifications": [
    {
      "id": "notif_001",
      "task_id": "task_001",
      "content": "【定时任务】查看股票 - 执行结果：\n今日上证指数...",
      "read": false,
      "created_at": "2026-03-03T09:00:00"
    }
  ],
  "unread_count": 1
}
```

---

## 数据模型

### SQLite 表结构

```sql
-- 用户表
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- 验证码表
CREATE TABLE verification_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(100) NOT NULL,
    code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 对话历史表
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### JSON 文件结构

```json
// data/tasks/{user_id}.json
{
  "user_id": 1,
  "tasks": [
    {
      "id": "task_001",
      "content": "查看股票",
      "cron": "0 9 * * *",
      "natural_language": "每天早上9点提醒我查看股票",
      "enabled": true,
      "created_at": "2026-03-03T10:00:00",
      "last_run": "2026-03-03T09:00:00"
    }
  ]
}

// data/notifications/{user_id}.json
{
  "user_id": 1,
  "notifications": [
    {
      "id": "notif_001",
      "task_id": "task_001",
      "content": "【定时任务】查看股票 - 执行结果：\n...",
      "read": false,
      "created_at": "2026-03-03T09:00:00"
    }
  ]
}
```

---

## 核心流程

### 1. 用户认证流程

```
┌─────────────────────────────────────────────────────────────┐
│                      用户认证流程                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  方式一：用户名密码                                          │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                │
│  │ 注册    │───▶│ 密码哈希 │───▶│ 存入DB  │                │
│  └─────────┘    └─────────┘    └─────────┘                │
│       │                                                    │
│       ▼                                                    │
│  ┌─────────┐    ┌─────────────┐    ┌─────────┐           │
│  │ 登录    │───▶│ 验证密码哈希 │───▶│ 返回JWT │           │
│  └─────────┘    └─────────────┘    └─────────┘           │
│                                                             │
│  方式二：邮箱验证码                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────┐       │
│  │ 输入邮箱    │───▶│ 发送验证码   │───▶│ 存入DB  │       │
│  └─────────────┘    └─────────────┘    └─────────┘       │
│       │                    │                               │
│       │                    ▼                               │
│       │             ┌─────────────┐    ┌─────────┐       │
│       │             │ 用户输入验证码│───▶│ 验证    │       │
│       │             └─────────────┘    └─────────┘       │
│       │                                      │            │
│       │                                      ▼            │
│       │                               ┌──────────────┐   │
│       │                               │ 新用户？注册  │   │
│       │                               │ 老用户？登录  │   │
│       │                               └──────────────┘   │
│       │                                      │            │
│       └──────────────────────────────────────┼───────────┘
│                                              ▼            │
│                                       ┌─────────┐        │
│                                       │ 返回JWT │        │
│                                       └─────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### 2. 对话流程

```
┌─────────────────────────────────────────────────────────────┐
│                        对话流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    WebSocket     ┌──────────┐               │
│  │ 前端     │◀───────────────▶│ 后端     │               │
│  └──────────┘                  └──────────┘               │
│       │                              │                     │
│       │ 发送消息                     │                     │
│       ├─────────────────────────────▶│                     │
│       │                              │                     │
│       │                     ┌────────▼────────┐           │
│       │                     │ iFlow SDK       │           │
│       │                     │ query_stream()  │           │
│       │                     └────────┬────────┘           │
│       │                              │                     │
│       │              ┌───────────────┼───────────────┐    │
│       │              ▼               ▼               ▼    │
│       │     AssistantMessage  ToolCallMessage  其他消息   │
│       │              │               │               │    │
│       │              ▼               ▼               ▼    │
│       │     流式推送文本      推送工具调用卡片    处理其他  │
│       │                              │                    │
│       │                              ▼                    │
│       │                     工具执行结果                   │
│       │                              │                    │
│       │◀─────────────────────────────┘                    │
│       │                              │                     │
│       │ 保存到 chat_history          │                     │
│       │                              │                     │
└─────────────────────────────────────────────────────────────┘
```

### 3. 定时任务流程

```
┌─────────────────────────────────────────────────────────────┐
│                      定时任务流程                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  创建任务                                                   │
│  ┌────────────────┐                                         │
│  │ 用户输入:       │                                         │
│  │ "每天早上9点    │                                         │
│  │  提醒我查看股票"│                                         │
│  └────────┬───────┘                                         │
│           │                                                 │
│           ▼                                                 │
│  ┌────────────────┐    ┌────────────────┐                  │
│  │ 调用 iFlow     │───▶│ 解析意图       │                  │
│  │ 解析自然语言    │    │ 提取时间和内容  │                  │
│  └────────────────┘    └────────┬───────┘                  │
│                                 │                           │
│                                 ▼                           │
│  ┌────────────────┐    ┌────────────────┐                  │
│  │ 生成 Cron 表达式│◀───│ type: daily    │                  │
│  │ "0 9 * * *"    │    │ time: 09:00    │                  │
│  └────────┬───────┘    │ content: 查看股票│                  │
│           │            └────────────────┘                  │
│           ▼                                                 │
│  ┌────────────────┐    ┌────────────────┐                  │
│  │ 添加到         │───▶│ 保存到         │                  │
│  │ APScheduler    │    │ JSON 文件      │                  │
│  └────────────────┘    └────────────────┘                  │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  执行任务                                                   │
│  ┌────────────────┐                                         │
│  │ APScheduler    │                                         │
│  │ 定时触发       │                                         │
│  └────────┬───────┘                                         │
│           │                                                 │
│           ▼                                                 │
│  ┌────────────────┐    ┌────────────────┐                  │
│  │ 调用 iFlow     │───▶│ 执行任务内容   │                  │
│  │ 执行任务        │    │ "查看股票"     │                  │
│  └────────────────┘    └────────┬───────┘                  │
│                                 │                           │
│                                 ▼                           │
│  ┌────────────────┐    ┌────────────────┐                  │
│  │ 获取执行结果   │───▶│ 保存到通知文件 │ (必须执行)       │
│  └────────────────┘    └────────┬───────┘                  │
│                                 │                           │
│                                 ▼                           │
│  ┌────────────────┐                                         │
│  │ 检查用户       │                                         │
│  │ 是否在线       │                                         │
│  └────────┬───────┘                                         │
│           │                                                 │
│     ┌─────┴─────┐                                           │
│     ▼           ▼                                           │
│  在线          离线                                          │
│     │           │                                           │
│     ▼           │                                           │
│  ┌──────────┐   │                                           │
│  │WebSocket │   │                                           │
│  │推送到聊天框│   │                                           │
│  └──────────┘   │                                           │
│                 │                                           │
│                 ▼                                           │
│           用户下次查看                                       │
│           通知栏                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 配置信息

### 邮件服务配置

```python
# config.py
EMAIL_CONFIG = {
    "smtp_server": "smtp.126.com",
    "smtp_port": 465,
    "smtp_user": "wsadfg142536@126.com",
    "smtp_password": "ZVes6dnvmUYV6iZM",
    "use_ssl": True
}
```

### iFlow SDK 配置

```python
# config.py
IFLOW_CONFIG = {
    "ws_url": "ws://localhost:8090/acp",
    "timeout": 300
}
```

### JWT 配置

```python
# config.py
JWT_CONFIG = {
    "secret_key": "your-secret-key-change-in-production",
    "algorithm": "HS256",
    "expire_minutes": 60 * 24 * 7  # 7天
}
```

---

## 依赖清单

### 后端 requirements.txt

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
websockets==12.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pydantic==2.5.3
pydantic-settings==2.1.0
apscheduler==3.10.4
aiosmtplib==3.0.1
iflow-cli-sdk
sqlalchemy==2.0.25
aiosqlite==0.19.0
```

### 前端 package.json (核心依赖)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.0",
    "axios": "^1.6.0",
    "marked": "^11.0.0",
    "highlight.js": "^11.9.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "typescript": "^5.3.0"
  }
}
```

---

## 实施步骤

### 阶段一：后端基础架构 (预计 2-3 小时)

1. **项目初始化**
   - 创建目录结构
   - 安装 Python 依赖
   - 配置 FastAPI 应用

2. **数据库层**
   - SQLite 数据库连接
   - 用户表、验证码表、聊天历史表
   - SQLAlchemy ORM 模型

3. **认证服务**
   - JWT 生成/验证
   - 密码哈希处理
   - 邮箱验证码发送/验证

### 阶段二：iFlow 集成与对话 (预计 2-3 小时)

1. **iFlow SDK 封装**
   - 连接管理
   - 流式对话处理
   - 工具调用处理

2. **WebSocket 服务**
   - 连接管理
   - 消息路由
   - 认证验证

3. **对话 API**
   - 发送消息
   - 历史记录查询

### 阶段三：定时任务系统 (预计 2-3 小时)

1. **任务调度器**
   - APScheduler 集成
   - 任务存储和加载

2. **自然语言解析**
   - 调用 iFlow 解析用户意图
   - 生成 Cron 表达式

3. **任务 API**
   - 创建/删除/查询任务
   - 启用/禁用任务

### 阶段四：通知系统 (预计 1-2 小时)

1. **通知存储**
   - JSON 文件读写
   - 按用户分类存储

2. **通知 API**
   - 查询通知列表
   - 标记已读/删除

3. **实时推送**
   - WebSocket 推送
   - 在线状态检测

### 阶段五：前端开发 (预计 4-5 小时)

1. **基础框架**
   - React 项目初始化
   - 路由配置
   - API 服务封装

2. **认证模块**
   - 登录/注册页面
   - 邮箱验证码输入
   - Token 管理

3. **对话模块**
   - 对话界面
   - 消息展示（支持 Markdown）
   - 工具调用卡片
   - 流式消息显示

4. **定时任务模块**
   - 任务列表
   - 自然语言创建
   - 任务管理

5. **通知模块**
   - 通知栏
   - 未读提示
   - 历史通知

6. **移动端适配**
   - 响应式布局
   - 触摸交互优化

### 阶段六：集成测试 (预计 1-2 小时)

1. **功能测试**
   - 用户注册/登录
   - 对话功能
   - 定时任务创建和执行
   - 通知推送

2. **移动端测试**
   - 不同屏幕尺寸
   - 触摸交互

3. **边界情况处理**
   - 网络断开重连
   - 任务执行失败
   - 大量消息处理

---

## 前端 UI 设计

### 页面布局

```
┌─────────────────────────────────────────────┐
│  Header                                     │
│  ┌─────────┐  ┌───────────┐  ┌───────────┐ │
│  │ Logo    │  │ 任务管理  │  │ 通知 🔔  │ │
│  └─────────┘  └───────────┘  └───────────┘ │
├─────────────────────────────────────────────┤
│                                             │
│  Chat Area                                  │
│  ┌─────────────────────────────────────┐   │
│  │ User: 你好                          │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │ Assistant: 你好！有什么可以帮助你的？│   │
│  │                                     │   │
│  │ [Tool Call Card]                    │   │
│  │ ┌─────────────────────────────┐     │   │
│  │ │ 🔧 get_weather              │     │   │
│  │ │ 参数: { city: "北京" }       │     │   │
│  │ │ 状态: ✅ 成功               │     │   │
│  │ │ 结果: 北京今天晴...          │     │   │
│  │ └─────────────────────────────┘     │   │
│  └─────────────────────────────────────┘   │
│                                             │
│                                             │
│                                             │
├─────────────────────────────────────────────┤
│  Input Area                                 │
│  ┌───────────────────────────────────────┐ │
│  │ 输入消息...                      [发送]│ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 移动端适配

```
┌─────────────────────┐
│  ≡  App    🔔  👤   │  <- 紧凑 Header
├─────────────────────┤
│                     │
│  消息列表           │
│  (全屏宽度)         │
│                     │
│                     │
│                     │
│                     │
├─────────────────────┤
│  [  输入框    ] [➤] │  <- 固定底部
└─────────────────────┘
```

---

## 风险与注意事项

1. **iFlow SDK 连接**
   - 确保 iFlow 服务在 `localhost:8090` 运行
   - 处理连接断开重连逻辑

2. **定时任务持久化**
   - 服务重启后需要重新加载任务到 APScheduler
   - 确保任务 ID 唯一性

3. **WebSocket 连接管理**
   - 用户可能打开多个标签页
   - 需要处理重复连接

4. **邮箱验证码**
   - 验证码有效期设置为 5 分钟
   - 限制发送频率（1 分钟 1 次）

5. **安全考虑**
   - JWT Token 存储在 localStorage
   - 密码使用 bcrypt 哈希
   - API 需要验证 Token

---

## 后续优化方向

1. **性能优化**
   - 消息分页加载
   - WebSocket 心跳检测
   - 任务执行结果缓存

2. **功能增强**
   - 对话导出
   - 多语言支持
   - 暗色主题

3. **部署优化**
   - Docker 容器化
   - Nginx 反向代理
   - HTTPS 支持
