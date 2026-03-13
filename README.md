# iFlow Chat

基于 iFlow SDK 的 AI 对话 Web 应用，支持实时流式对话、定时任务管理和手机推送通知。

## 功能特性

- 🔐 **多种认证方式** - 用户名密码登录、邮箱验证码登录
- 💬 **实时流式对话** - WebSocket 驱动的流式 AI 响应
- 📅 **定时任务管理** - 支持 Cron 表达式的智能任务调度
- 🔔 **实时通知** - WebSocket 推送的任务提醒和系统通知
- 📱 **PushMe 推送** - 任务完成时推送消息到手机
- 📎 **文件附件** - 支持图片等文件上传处理
- 🎨 **多会话管理** - 支持多对话切换和历史记录
- 🌙 **深色主题** - 支持亮色/暗色主题切换

## 技术栈

### 后端

| 技术 | 版本 | 说明 |
|------|------|------|
| FastAPI | >= 0.111.0 | Web 框架 |
| SQLite | - | 主数据库 (aiosqlite 异步驱动) |
| Redis | >= 5.0.0 | 缓存 / 消息队列 / 会话存储 |
| SQLAlchemy | >= 2.0.25 | ORM |
| Pydantic | >= 2.5.3 | 数据验证 |
| APScheduler | 3.10.4 | 任务调度 |
| iFlow CLI SDK | latest | AI 对话 SDK |
| JWT | - | 认证授权 |
| WebSocket | - | 实时通信 |

### 前端

| 技术 | 版本 | 说明 |
|------|------|------|
| React | 19.x | UI 框架 |
| TypeScript | 4.9.x | 类型安全 |
| React Router | 6.x | 路由管理 |
| Axios | 1.x | HTTP 客户端 |
| marked | 17.x | Markdown 解析 |
| highlight.js | 11.x | 代码高亮 |

## 项目结构

```
mybot/
├── backend/                 # 后端服务
│   ├── main.py             # 应用入口
│   ├── config.py           # 配置管理
│   ├── database.py         # 数据库连接
│   ├── models/             # 数据模型
│   │   ├── schemas.py      # Pydantic 模型
│   │   └── user.py         # ORM 模型
│   ├── routers/            # API 路由
│   │   ├── auth.py         # 认证接口
│   │   ├── chat.py         # 对话接口
│   │   ├── tasks.py        # 任务接口
│   │   ├── notifications.py # 通知接口
│   │   └── websocket.py    # WebSocket 接口
│   ├── services/           # 业务服务
│   │   ├── auth.py         # 认证服务
│   │   ├── iflow_client.py # iFlow SDK 封装
│   │   ├── scheduler.py    # 任务调度器
│   │   ├── task_parser.py  # 任务解析
│   │   └── email_service.py # 邮件服务
│   └── tests/              # 测试用例
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/     # UI 组件
│   │   │   ├── Auth/       # 认证组件
│   │   │   ├── Chat/       # 聊天组件
│   │   │   ├── TaskManager/# 任务管理
│   │   │   └── Notification/# 通知组件
│   │   ├── contexts/       # React Context
│   │   ├── hooks/          # 自定义 Hooks
│   │   ├── services/       # API 服务
│   │   └── types/          # TypeScript 类型
│   └── package.json
└── data/                   # 数据存储
    ├── tasks/              # 任务数据
    └── notifications/      # 通知数据
```

## 快速开始

### 环境要求

- Python >= 3.11
- Node.js >= 16
- iFlow CLI (需要单独安装)

### 后端启动

```bash
# 进入后端目录
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 生产环境启动
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm start

# 生产构建
npm run build
```

### 环境变量

**后端 (backend/config.py)**

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `JWT_SECRET_KEY` | JWT 密钥 | `your-secret-key-change-in-production` |
| `DATABASE_URL` | 数据库路径 | `./data/app.db` |
| `IFLOW_WS_URL` | iFlow WebSocket 地址 | `ws://localhost:8090/acp` |
| `SMTP_HOST` | SMTP 服务器 | `smtp.126.com` |
| `SMTP_USER` | SMTP 用户名 | - |
| `SMTP_PASSWORD` | SMTP 密码 | - |

**前端 (.env)**

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `REACT_APP_API_URL` | 后端 API 地址 | `http://localhost:8000/api` |
| `REACT_APP_WS_HOST` | WebSocket 主机 | `localhost:8000` |

## API 接口

### 认证 `/api/auth`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/register` | 用户注册 |
| POST | `/login` | 用户登录 |
| POST | `/send-code` | 发送邮箱验证码 |
| POST | `/verify-code` | 验证码登录 |
| GET | `/me` | 获取当前用户 |

### 对话 `/api/chat`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/` | 发送消息 |
| GET | `/history` | 获取聊天历史 |
| DELETE | `/history` | 清空历史 |

### 定时任务 `/api/tasks`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/` | 创建任务 |
| GET | `/` | 任务列表 |
| GET | `/{task_id}` | 任务详情 |
| DELETE | `/{task_id}` | 删除任务 |
| POST | `/{task_id}/toggle` | 启用/禁用 |

### WebSocket

```
ws://server/ws?token=<jwt_token>
```

## 测试

```bash
# 后端测试
cd backend
pytest

# 前端测试
cd frontend
npm test
```

## ACP 进程管理

项目实现了基于用户 ID 的 ACP (Agent Communication Protocol) 进程管理：

- **端口池管理** - 动态分配端口 (8091-9000)
- **用户隔离** - 每个用户独立的进程和端口栈
- **智能清理** - 任务完成后自动清理旧进程
- **并发安全** - 支持高并发场景下的资源管理

## 部署建议

1. **JWT 密钥** - 生产环境务必修改 `JWT_SECRET_KEY`
2. **HTTPS** - 建议配置 SSL 证书
3. **数据库** - 可切换到 PostgreSQL/MySQL
4. **进程管理** - 使用 systemd 或 Docker
5. **反向代理** - 使用 Nginx 处理静态文件和负载均衡

## License

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
