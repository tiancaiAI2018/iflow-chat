# AI 开发计划：mybot-mobile (React Native)

## 项目概述

| 项目 | 路径 | 技术栈 |
|------|------|--------|
| 源项目 | `/root/.iflow-bot/workspace/mybot/frontend` | React 19 + TypeScript + WebSocket |
| 目标项目 | `/root/.iflow-bot/workspace/mybot-mobile` | React Native (Expo SDK 52) + TypeScript |

**目标输出**: 安卓 APK（支持 API 24+，即 Android 7.0+）

---

## 源项目文件清单

```
frontend/src/
├── contexts/
│   ├── ChatContext.tsx          # 聊天状态管理 (WebSocket)
│   └── NotificationContext.tsx  # 通知状态管理
├── services/
│   └── api.ts                   # API 封装 (Axios)
├── types/
│   └── index.ts                 # TypeScript 类型定义
├── hooks/
│   ├── useAuth.ts              # 认证状态 Hook
│   ├── useWebSocket.ts         # WebSocket Hook
│   └── useNotifications.ts     # 通知 Hook
├── components/
│   ├── Auth/
│   │   ├── Login.tsx           # 用户名密码登录
│   │   ├── Register.tsx        # 用户注册
│   │   └── LoginEmail.tsx      # 邮箱验证码登录
│   ├── Chat/
│   │   ├── Chat.tsx            # 聊天主页面
│   │   ├── Message.tsx         # 消息渲染
│   │   ├── MessageInput.tsx    # 消息输入框
│   │   ├── NewChatButton.tsx   # 新建会话按钮
│   │   └── HistoryButton.tsx   # 历史记录按钮
│   ├── Conversation/
│   │   ├── ConversationDrawer.tsx   # 会话列表抽屉
│   │   └── ConversationItem.tsx     # 会话项
│   ├── TaskManager/
│   │   ├── TaskManager.tsx     # 任务管理主页
│   │   ├── TaskList.tsx        # 任务列表
│   │   └── TaskCreator.tsx     # 任务创建
│   ├── Notification/
│   │   ├── NotificationBar.tsx # 通知栏
│   │   └── NotificationItem.tsx# 通知项
│   ├── ToolCall/
│   │   └── ToolCall.tsx        # 工具调用展示
│   ├── Workspace/
│   │   ├── WorkspaceSelectModal.tsx  # 工作区选择弹窗
│   │   └── DirectoryTree.tsx   # 目录树
│   └── Layout/
│       └── Header.tsx          # 顶部导航
```

---

## 文件迁移映射

### 完全复制（无需修改）

| 源文件 | 目标文件 | 说明 |
|--------|----------|------|
| `contexts/ChatContext.tsx` | `contexts/ChatContext.tsx` | 业务逻辑不变，仅改 WebSocket URL |
| `contexts/NotificationContext.tsx` | `contexts/NotificationContext.tsx` | 完全不变 |
| `services/api.ts` | `services/api.ts` | 基地址改公网 IP |
| `types/index.ts` | `types/index.ts` | 完全不变 |

### 适配迁移（修改存储层）

| 源文件 | 目标文件 | 修改内容 |
|--------|----------|----------|
| `hooks/useAuth.ts` | `hooks/useAuth.ts` | `localStorage` → `AsyncStorage` |
| `hooks/useWebSocket.ts` | `hooks/useWebSocket.ts` | 保持不变 |
| `hooks/useNotifications.ts` | `hooks/useNotifications.ts` | 保持不变 |

### 组件重写（RN 适配）

| 源组件 | 目标 Screen | 主要改动 |
|--------|-------------|----------|
| `Auth/Login.tsx` | `screens/auth/LoginScreen.tsx` | Paper TextInput + Button |
| `Auth/Register.tsx` | `screens/auth/RegisterScreen.tsx` | Paper 组件 |
| `Auth/LoginEmail.tsx` | `screens/auth/LoginEmailScreen.tsx` | 验证码输入适配 |
| `Chat/Chat.tsx` | `screens/ChatScreen.tsx` | FlatList + KeyboardAvoidingView |
| `Chat/Message.tsx` | `components/Message.tsx` | Markdown 渲染适配 |
| `Chat/MessageInput.tsx` | `components/MessageInput.tsx` | TextInput + 发送按钮 |
| `Conversation/ConversationDrawer.tsx` | `screens/ConversationScreen.tsx` | FlatList 会话列表 |
| `TaskManager/TaskManager.tsx` | `screens/TaskScreen.tsx` | Paper Card + FAB |
| `Notification/NotificationBar.tsx` | `screens/NotificationScreen.tsx` | FlatList + Badge |
| `Workspace/WorkspaceSelectModal.tsx` | `components/WorkspaceModal.tsx` | Paper Modal |

---

## 技术选型

### UI 组件库
- **React Native Paper 5.x** - Material Design 3
- 配色：深色主题 + 渐变色（紫蓝渐变）

### 导航
- **React Navigation 7.x**
- Stack Navigator（主导航） + Tab Navigator（底部导航）

### 存储
- **AsyncStorage** - Token、用户信息持久化

### Markdown
- **react-native-markdown-display** - 聊天消息渲染

### 图标
- **@expo/vector-icons** - MaterialCommunityIcons

---

## API 配置

```typescript
// config/api.ts
export const API_BASE_URL = 'http://120.53.45.173:8000/api';
export const WS_BASE_URL = 'ws://120.53.45.173:8000/ws';
```

---

## 依赖安装清单

```bash
# 创建项目
npx create-expo-app@latest mybot-mobile --template blank-typescript
cd mybot-mobile

# 导航
npm install @react-navigation/native @react-navigation/native-stack @react-navigation/bottom-tabs
npx expo install react-native-screens react-native-safe-area-context

# UI
npm install react-native-paper
npx expo install react-native-vector-icons @expo/vector-icons

# 存储
npm install @react-native-async-storage/async-storage

# HTTP
npm install axios

# Markdown
npm install react-native-markdown-display

# 手势动画（导航依赖）
npm install react-native-gesture-handler react-native-reanimated

# 图库选择（头像等功能预留）
npx expo install expo-image-picker
```

---

## 项目结构

```
mybot-mobile/
├── app.json                  # Expo 配置
├── App.tsx                   # 入口 + 导航配置
├── babel.config.js           # Babel 配置（reanimated 插件）
├── tsconfig.json
├── src/
│   ├── config/
│   │   └── api.ts            # API 地址配置
│   ├── contexts/
│   │   ├── ChatContext.tsx
│   │   └── NotificationContext.tsx
│   ├── services/
│   │   └── api.ts
│   ├── types/
│   │   └── index.ts
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useWebSocket.ts
│   │   └── useNotifications.ts
│   ├── screens/
│   │   ├── auth/
│   │   │   ├── LoginScreen.tsx
│   │   │   ├── RegisterScreen.tsx
│   │   │   └── LoginEmailScreen.tsx
│   │   ├── ChatScreen.tsx
│   │   ├── ConversationScreen.tsx
│   │   ├── TaskScreen.tsx
│   │   └── NotificationScreen.tsx
│   ├── components/
│   │   ├── Message.tsx
│   │   ├── MessageInput.tsx
│   │   ├── WorkspaceModal.tsx
│   │   ├── DirectoryTree.tsx
│   │   └── ToolCall.tsx
│   ├── navigation/
│   │   ├── AuthStack.tsx     # 未登录导航
│   │   ├── MainStack.tsx     # 已登录导航
│   │   └── MainTab.tsx       # 底部 Tab 导航
│   └── theme/
│       └── theme.ts          # Paper 主题配置
└── assets/
    ├── icon.png              # App 图标 (1024x1024)
    ├── adaptive-icon.png     # Android 自适应图标
    └── splash.png            # 启动屏
```

---

## 任务清单

### Phase 1: 项目初始化
1. [ ] 创建 Expo 项目，安装所有依赖
2. [ ] 配置 babel.config.js（reanimated 插件）
3. [ ] 配置 app.json（权限、图标、启动屏）

### Phase 2: 核心逻辑迁移
4. [ ] 复制 `types/index.ts`
5. [ ] 复制并适配 `services/api.ts`
6. [ ] 复制 `contexts/ChatContext.tsx`，修改 WebSocket URL
7. [ ] 复制 `contexts/NotificationContext.tsx`
8. [ ] 适配 `hooks/useAuth.ts`（AsyncStorage）

### Phase 3: 导航配置
9. [ ] 创建 AuthStack（登录、注册、邮箱登录）
10. [ ] 创建 MainTab（聊天、任务、通知）
11. [ ] 创建 MainStack（包含 Tab + Modal）
12. [ ] 配置 App.tsx 入口

### Phase 4: 认证页面
13. [ ] LoginScreen - 用户名密码登录
14. [ ] RegisterScreen - 用户注册
15. [ ] LoginEmailScreen - 邮箱验证码登录

### Phase 5: 聊天功能
16. [ ] ChatScreen - 聊天主页面
17. [ ] Message 组件 - Markdown 消息渲染
18. [ ] MessageInput 组件 - 输入框 + 发送
19. [ ] ConversationScreen - 会话列表

### Phase 6: 任务与通知
20. [ ] TaskScreen - 任务管理页面
21. [ ] NotificationScreen - 通知列表

### Phase 7: 主题与适配
22. [ ] 配置 Paper 深色主题
23. [ ] Android 返回键处理
24. [ ] 软键盘适配（KeyboardAvoidingView）
25. [ ] 状态栏沉浸

### Phase 8: 构建与测试
26. [ ] 准备 App 图标和启动屏资源
27. [ ] 配置 EAS Build
28. [ ] 构建 APK：`eas build -p android`
29. [ ] 真机安装测试

---

## Android 权限配置

```json
// app.json
{
  "expo": {
    "android": {
      "permissions": [
        "INTERNET",
        "ACCESS_NETWORK_STATE"
      ]
    }
  }
}
```

---

## 注意事项

1. **WebSocket 连接**：确保后端服务在 `120.53.45.173:8000` 可访问
2. **软键盘**：聊天页面必须使用 `KeyboardAvoidingView`
3. **Markdown 渲染**：测试工具调用、代码块的显示效果
4. **Token 过期**：401 响应需要跳转登录页
5. **网络状态**：添加网络错误提示

---

## Web → RN 组件对照

| Web | React Native |
|-----|--------------|
| `<div>` | `<View>` |
| `<span>`, `<p>` | `<Text>` |
| `<input>` | `<TextInput>` |
| `<button>` | `<Button>` / `<TouchableOpacity>` |
| `localStorage` | `AsyncStorage` |
| `window.location.href` | `navigation.navigate()` |
| CSS 文件 | `StyleSheet.create()` |
| `onClick` | `onPress` |
| `onKeyDown` | `onKeyPress` |
