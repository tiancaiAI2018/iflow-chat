# AGENTS.md - 前端项目指南

这是 iFlow 聊天机器人的前端项目，一个基于 React + TypeScript 的 Web 应用。

## 项目概述

- **项目类型**：React 单页应用 (SPA)
- **技术栈**：React 19 + TypeScript + React Router + Axios + WebSocket
- **主要功能**：
  - 用户认证（用户名密码登录、邮箱验证码登录、注册）
  - 实时聊天（WebSocket 流式响应）
  - 定时任务管理（创建、删除、启用/禁用）
  - 通知系统（实时推送、已读/未读状态）

## 项目结构

```
src/
├── components/          # UI 组件
│   ├── Auth/           # 认证组件（登录、注册、邮箱登录）
│   ├── Chat/           # 聊天组件（消息列表、输入框）
│   ├── Layout/         # 布局组件（Header）
│   ├── Notification/   # 通知组件（通知栏、通知项）
│   ├── TaskManager/    # 任务管理组件（创建任务、任务列表）
│   └── ToolCall/       # 工具调用显示组件
├── contexts/           # React Context
│   ├── ChatContext.tsx # 聊天上下文（WebSocket 连接、消息状态）
│   └── NotificationContext.tsx
├── hooks/              # 自定义 Hooks
│   ├── useAuth.ts      # 认证状态管理
│   ├── useNotifications.ts
│   └── useWebSocket.ts
├── services/           # API 服务
│   └── api.ts          # Axios API 封装
├── types/              # TypeScript 类型定义
│   └── index.ts
├── App.tsx             # 应用入口
└── index.tsx          # React 渲染入口
```

## 运行命令

```bash
# 开发模式（http://localhost:3000）
npm start

# 生产构建
npm run build

# 运行测试
npm test
```

## 开发约定

- **组件开发**：使用函数组件 + Hooks
- **样式**：CSS 模块（`*.css` 文件与组件同目录）
- **API 调用**：通过 `services/api.ts` 中的 `apiService` 单例
- **类型定义**：统一在 `types/index.ts` 中定义
- **路由**：使用 `react-router-dom`，受保护路由需要登录

## 环境变量

- `REACT_APP_API_URL` - 后端 API 地址（默认 `http://localhost:8000/api`）
- `REACT_APP_WS_HOST` - WebSocket 主机地址（默认 `localhost:8000`）

## 主要页面路由

| 路径 | 说明 |
|------|------|
| `/login` | 用户名密码登录 |
| `/login-email` | 邮箱验证码登录 |
| `/register` | 用户注册 |
| `/chat` | 聊天主页（默认） |
| `/tasks` | 任务管理 |
| `/notifications` | 通知中心 |

## 注意事项

- WebSocket 自动重连最多 5 次
- 认证 Token 存储在 localStorage
- 401 响应会自动清除登录状态并跳转登录页
