# iFlow CLI SDK 使用指南

> 基于实际测试验证的完整文档
> SDK 版本: 0.1.3 | 协议版本: 1

## 安装

```bash
pip install iflow-cli-sdk
```

## 快速开始

### 1. 简单查询

```python
from iflow_sdk import query
import asyncio

async def main():
    response = await query("你好")
    print(response)

asyncio.run(main())
```

### 2. 流式响应

```python
from iflow_sdk import query_stream
import asyncio

async def main():
    async for chunk in query_stream("解释量子计算"):
        print(chunk, end="", flush=True)

asyncio.run(main())
```

### 3. 同步调用

```python
from iflow_sdk import query_sync

response = query_sync("1+1等于几？")
print(response)
```

## 核心组件

### IFlowClient - 主客户端

用于复杂的交互场景，支持会话保持和多轮对话：

```python
from iflow_sdk import IFlowClient, IFlowOptions

options = IFlowOptions(
    url="ws://localhost:8090/acp",  # WebSocket 地址
    auto_start_process=False,        # 手动模式（连接已有服务）
    timeout=60.0                     # 超时时间（秒）
)

async with IFlowClient(options) as client:
    # 发送消息
    await client.send_message("你的问题")
    
    # 接收响应
    async for message in client.receive_messages():
        # 处理消息...
        pass
```

### IFlowOptions 配置选项

| 参数 | 类型 | 说明 |
|------|------|------|
| `url` | str | WebSocket 地址 (默认: ws://localhost:8090/acp) |
| `cwd` | str | 工作目录 |
| `timeout` | float | 超时时间（秒） |
| `auto_start_process` | bool | 是否自动启动 iFlow 进程 |
| `approval_mode` | ApprovalMode | 审批模式 |
| `log_level` | str | 日志级别 |
| `session_id` | str | 会话 ID（用于恢复会话） |

### ApprovalMode 审批模式

```python
from iflow_sdk import ApprovalMode

ApprovalMode.DEFAULT   # 默认模式，需要确认
ApprovalMode.AUTO_EDIT # 自动编辑
ApprovalMode.PLAN      # 计划模式
ApprovalMode.YOLO      # 全自动模式
```

## 消息类型

### AssistantMessage - AI 响应

```python
from iflow_sdk import AssistantMessage

async for message in client.receive_messages():
    if isinstance(message, AssistantMessage):
        text = message.chunk.text  # 文本片段
        agent_id = message.agent_id  # 代理 ID（如果有）
```

### ToolCallMessage - 工具调用

```python
from iflow_sdk import ToolCallMessage, ToolCallStatus

async for message in client.receive_messages():
    if isinstance(message, ToolCallMessage):
        print(f"工具: {message.tool_name}")
        print(f"状态: {message.status}")
        
        if message.status == ToolCallStatus.COMPLETED:
            print(f"结果: {message.result}")
        elif message.status == ToolCallStatus.FAILED:
            print(f"错误: {message.error}")
```

**ToolCallStatus 状态值：**
- `PENDING` - 等待中
- `IN_PROGRESS` - 执行中
- `COMPLETED` - 完成
- `FAILED` - 失败

### TaskFinishMessage - 任务完成

```python
from iflow_sdk import TaskFinishMessage, StopReason

async for message in client.receive_messages():
    if isinstance(message, TaskFinishMessage):
        print(f"停止原因: {message.stop_reason}")
        break  # 结束消息循环
```

**StopReason 值：**
- `END_TURN` - 正常结束
- `MAX_TOKENS` - 达到最大 token 限制
- `CANCELLED` - 被取消
- `REFUSAL` - 拒绝执行

### PlanMessage - 任务计划

```python
from iflow_sdk import PlanMessage

async for message in client.receive_messages():
    if isinstance(message, PlanMessage):
        for entry in message.entries:
            print(f"[{entry.status}] {entry.content}")
```

## 原始协议数据

使用 `RawDataClient` 查看原始 JSON-RPC 协议数据：

```python
from iflow_sdk import RawDataClient, IFlowOptions

options = IFlowOptions(url="ws://localhost:8090/acp", auto_start_process=False)
client = RawDataClient(options=options)

await client.connect()

async for raw_msg in client.receive_raw_messages():
    print(f"类型: {raw_msg.message_type}")
    print(f"数据: {raw_msg.json_data}")
```

### 协议格式

协议基于 JSON-RPC 2.0，主要消息类型：

**会话更新 (method:session/update)：**
```json
{
  "jsonrpc": "2.0",
  "method": "session/update",
  "params": {
    "sessionId": "xxx",
    "update": {
      "sessionUpdate": "agent_message_chunk",
      "content": { "type": "text", "text": "响应文本" }
    }
  }
}
```

**任务完成 (response)：**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": { "stopReason": "end_turn" }
}
```

## 完整示例

### 交互式聊天机器人

```python
#!/usr/bin/env python3
import asyncio
from iflow_sdk import IFlowClient, IFlowOptions, AssistantMessage, TaskFinishMessage

async def chatbot():
    options = IFlowOptions(
        url="ws://localhost:8090/acp",
        auto_start_process=False
    )
    
    async with IFlowClient(options) as client:
        while True:
            user_input = input("你: ")
            if user_input.lower() in ['quit', 'exit']:
                break
            
            await client.send_message(user_input)
            print("助手: ", end="", flush=True)
            
            async for message in client.receive_messages():
                if isinstance(message, AssistantMessage):
                    print(message.chunk.text, end="", flush=True)
                elif isinstance(message, TaskFinishMessage):
                    print()
                    break

asyncio.run(chatbot())
```

### 带工具调用的任务

```python
#!/usr/bin/env python3
import asyncio
from iflow_sdk import (
    IFlowClient, IFlowOptions,
    AssistantMessage, ToolCallMessage, TaskFinishMessage, ToolCallStatus
)

async def task_example():
    options = IFlowOptions(
        url="ws://localhost:8090/acp",
        auto_start_process=False,
        timeout=120.0
    )
    
    async with IFlowClient(options) as client:
        # 执行需要工具调用的任务
        await client.send_message("列出当前目录的文件")
        
        async for message in client.receive_messages():
            if isinstance(message, AssistantMessage):
                print(message.chunk.text, end="", flush=True)
            elif isinstance(message, ToolCallMessage):
                if message.status == ToolCallStatus.PENDING:
                    print(f"\n[调用工具: {message.tool_name}]")
            elif isinstance(message, TaskFinishMessage):
                print("\n[完成]")
                break

asyncio.run(task_example())
```

## 错误处理

```python
from iflow_sdk import (
    IFlowClient, IFlowOptions,
    ConnectionError, TimeoutError, ProtocolError
)

try:
    async with IFlowClient(options) as client:
        await client.send_message("测试")
        # ...
except ConnectionError as e:
    print(f"连接错误: {e}")
except TimeoutError as e:
    print(f"超时错误: {e}")
except ProtocolError as e:
    print(f"协议错误: {e}")
```

## 注意事项

1. **Python 版本**：SDK 安装在 Python 3.12，使用 `python3.12` 运行脚本
2. **服务启动**：使用手动模式时，需先启动 iFlow ACP 服务：
   ```bash
   iflow --experimental-acp --port 8090
   ```
3. **会话保持**：在同一个 `IFlowClient` 连接中发送多条消息可保持会话上下文
4. **流式响应**：文本通过 `agent_message_chunk` 消息逐块发送
5. **结束检测**：通过 `TaskFinishMessage` 判断响应结束

## 测试文件

| 文件 | 说明 |
|------|------|
| `test_basic.py` | 基础连接测试 |
| `test_query.py` | query/query_stream 测试 |
| `test_messages.py` | 消息类型测试 |
| `test_toolcall.py` | 多工具调用测试 |
| `test_session.py` | 会话保持测试 |
| `test_raw.py` | 原始协议数据测试 |
| `test_sync.py` | 同步调用测试 |
