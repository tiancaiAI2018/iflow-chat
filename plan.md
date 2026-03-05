# 工作目录功能实现计划

## 目标
1. 使用 iFlow SDK 自动管理模式（auto_start_process=True），让它自己管理进程
2. 新会话和切换会话时都要断开旧的 iflow_client 再重新连接
3. 前端添加工作目录下拉选择，只能从 `/root/.iflow-bot/workspace` 下选择
4. 创建新会话前必须让用户选择工作目录，切换到旧会话就用旧会话的工作目录

---

## 一、后端修改

### 1. 数据库模型 (`backend/models/user.py`)
- Conversation 模型添加 `working_directory` 字段
- 默认值：`/root/.iflow-bot/workspace`

```python
working_directory = Column(String(500), default="/root/.iflow-bot/workspace")
```

### 2. iFlow 客户端服务 (`backend/services/iflow_client.py`)
- IFlowClientService 添加 `cwd` 参数
- IFlowOptions 设置 `auto_start_process=True` 和 `cwd`，不指定 url（使用默认）

```python
def __init__(
    self,
    cwd: Optional[str] = None,  # 工作目录
    timeout: Optional[float] = None,
    session_id: Optional[str] = None,
):
    self.cwd = cwd or "/root/.iflow-bot/workspace"
    # ...

async def connect(self) -> None:
    self._options = IFlowOptions(
        auto_start_process=True,  # 自动管理模式
        cwd=self.cwd,             # 工作目录
        timeout=self.timeout,
        session_id=self.session_id,
    )
    # 不指定 url，使用默认
```

### 3. WebSocket 路由 (`backend/routers/websocket.py`)

#### handle_switch_conversation
- 先 `disconnect()` 旧的 iflow_client
- 用会话的 `working_directory` 创建新连接

#### handle_chat_message（创建新会话时）
- 先 `disconnect()` 旧的 iflow_client
- 用用户选择的 `working_directory` 创建新连接

### 4. 会话 API (`backend/routers/conversations.py`)
- 创建会话时接收 `working_directory` 参数
- 保存到数据库

### 5. 新增目录列表 API
```
GET /api/directories
```
- 返回 `/root/.iflow-bot/workspace` 下的目录树结构
- 支持递归获取子目录

```json
{
  "directories": [
    {
      "name": "mybot",
      "path": "/root/.iflow-bot/workspace/mybot",
      "children": [...]
    },
    {
      "name": "projects",
      "path": "/root/.iflow-bot/workspace/projects",
      "children": [...]
    }
  ]
}
```

---

## 二、前端修改

### 1. 类型定义 (`frontend/src/types/index.ts`)
```typescript
interface Conversation {
  id: number;
  title: string;
  working_directory: string;  // 新增
  created_at: string;
  updated_at: string;
}
```

### 2. 新增目录选择组件 (`frontend/src/components/Workspace/DirectoryTree.tsx`)
- 树形结构，可展开/折叠
- 从 `/root/.iflow-bot/workspace` 下选择
- 支持选择根目录 workspace 本身
- 单选模式

### 3. 修改创建会话流程 (`frontend/src/contexts/ChatContext.tsx`)
- 点击"新对话"时弹出目录选择对话框（Modal）
- 用户选择工作目录后创建会话
- 发送 `working_directory` 到后端

### 4. 会话抽屉显示工作目录 (`frontend/src/components/Conversation/ConversationDrawer.tsx`)
- 每个会话项显示工作目录名称

---

## 三、数据库迁移

现有会话需要设置默认工作目录：
```sql
UPDATE conversations SET working_directory = '/root/.iflow-bot/workspace' WHERE working_directory IS NULL;
```

---

## 四、关键点

1. **自动管理模式**：`auto_start_process=True`，iFlow SDK 会自动启动和管理进程
2. **工作目录**：通过 `cwd` 参数指定，每个会话可以有不同的工作目录
3. **连接管理**：每次创建/切换会话时断开旧连接，创建新连接
4. **用户选择**：前端提供树形目录选择器，限制在 workspace 目录下
