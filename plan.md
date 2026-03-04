## 历史会话 + 新会话功能实现计划

### 一、后端修改

#### 1. 数据模型 (`backend/models/user.py`)
- 新增 `Conversation` 表：`id`, `user_id`, `title`, `iflow_session_id`, `created_at`, `updated_at`
- `ChatHistory` 表添加 `conversation_id` 外键

#### 2. Schema 定义 (`backend/models/schemas.py`)
- `ConversationCreate`, `ConversationResponse`, `ConversationListResponse`, `ConversationTitleUpdate`

#### 3. 新增会话路由 (`backend/routers/conversations.py`)
- `GET /` - 获取用户会话列表
- `POST /` - 创建新会话（AI 生成标题）
- `GET /{id}` - 获取会话详情 + 消息历史
- `DELETE /{id}` - 删除会话
- `PUT /{id}/title` - 更新会话标题

#### 4. 修改现有路由
- `routers/chat.py`: 按会话查询历史，移除清空端点
- `routers/websocket.py`: 消息关联到当前会话

---

### 二、前端修改

#### 1. 类型定义 (`frontend/src/types/index.ts`)
- 添加 `Conversation` 接口

#### 2. API 服务 (`frontend/src/services/api.ts`)
- 会话 CRUD 方法

#### 3. ChatContext 状态管理
- `currentConversationId`, `conversations` 状态
- `switchConversation()`, `createNewConversation()` 方法

#### 4. 新增 UI 组件
- `ConversationDrawer.tsx` - 抽屉式会话列表
- `ConversationItem.tsx` - 单个会话项
- `NewChatButton.tsx` - 新建会话按钮

#### 5. 布局调整
- 左上角新建会话按钮
- 左上角历史会话按钮（打开抽屉）
- 移除清空聊天按钮

---

### 三、实现顺序
1. 后端数据模型 → 2. 后端 API → 3. 前端类型和 API → 4. 前端状态管理 → 5. 前端 UI → 6. 联调测试

---

### 四、用户需求确认
- **标题生成**: AI 生成（从首条消息生成简短标题）
- **UI 布局**: 抽屉式（点击按钮滑出会话列表）
- **功能保留**: 移除清空按钮，改用删除会话功能