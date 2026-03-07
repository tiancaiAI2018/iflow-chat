# ACP 进程管理改造方案

## 背景问题

iFlow SDK 自启动模式不支持 `--stream` 参数，导致 AI 响应不是流式输出，而是一次性返回完整内容。

**根本原因**：
- SDK `process_manager.py:175` 硬编码启动命令：`[iflow, "--experimental-acp", "--port", port]`
- 缺少 `--stream` 参数
- `IFlowOptions` 无 `process_args` 配置项

## 解决方案

放弃 SDK 自动启动，改为手动管理 ACP 进程：
1. 连接前手动启动带 `--stream` 的 ACP 进程
2. SDK 使用 `auto_start_process=False` 连接已有服务
3. 断开时清理 ACP 进程

---

## 架构设计

### 整体流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           IFlowClientService                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   connect()                                                                 │
│       │                                                                     │
│       ├── 1. 查找可用端口（最多重试 10 次）                                   │
│       │                                                                     │
│       ├── 2. 启动 ACP 进程                                                   │
│       │       iflow --experimental-acp --stream --port {port}              │
│       │                                                                     │
│       ├── 3. 端口入栈                                                        │
│       │       _user_ports[user_id] = [port_new, port_old, ...]             │
│       │                                                                     │
│       └── 4. SDK 连接                                                        │
│               IFlowOptions(url="ws://localhost:{port}/acp",                │
│                           auto_start_process=False)                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           断开逻辑                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   TaskFinishMessage 到达时：                                                 │
│       │                                                                     │
│       ├── 端口栈长度 = 1                                                     │
│       │       → 不断开，保持连接                                             │
│       │                                                                     │
│       ├── 端口栈长度 > 1 且当前端口不是栈顶                                    │
│       │       → 断开当前端口（旧的 ACP）                                      │
│       │       → 从栈中移除                                                   │
│       │                                                                     │
│       └── 当前端口是栈顶（最新的）                                            │
│               → 不断开                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 端口栈管理

```
用户 A 端口栈：
  连接1: [8091]           → TaskFinishMessage → 不变（只有一个）
  连接2: [8092, 8091]     → 8091 输出完 → [8092]
  连接3: [8093, 8092, 8091] → 8091 输出完 → [8093, 8092]

用户 B 端口栈：
  连接1: [8094]           → 保持
```

---

## 配置项

```python
# backend/config.py

# ACP 进程管理配置
ACP_PORT_START: int = 8091        # 端口起始
ACP_PORT_END: int = 9000          # 端口结束（支持约 900 个并发）
ACP_MAX_PORT_RETRIES: int = 10    # 每次分配端口时最大重试次数
ACP_STARTUP_TIMEOUT: float = 5.0  # 进程启动超时（秒）
```

---

## 文件改动清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/config.py` | 修改 | 添加 ACP 进程配置项 |
| `backend/services/iflow_client.py` | 修改 | 集成 ACP 进程管理逻辑 |

---

## 核心代码设计

### 1. 类属性

```python
class IFlowClientService:
    # ACP 进程管理
    _port_processes: Dict[int, asyncio.subprocess.Process] = {}  # port -> process
    _user_ports: Dict[int, List[int]] = {}  # user_id -> [port_new, port_old, ...]
    _used_ports: Set[int] = set()  # 已使用的端口集合
    _lock: asyncio.Lock = asyncio.Lock()  # 端口分配锁
```

### 2. 端口查找

```python
async def _find_available_port(self, user_id: int) -> int:
    """查找可用端口"""
    async with self._lock:
        for i in range(config.ACP_MAX_PORT_RETRIES):
            # 基于用户 ID 和尝试次数计算端口
            base = config.ACP_PORT_START + (user_id * 10) + i
            port = base % (config.ACP_PORT_END - config.ACP_PORT_START + 1) + config.ACP_PORT_START
            
            if port not in self._used_ports and self._is_port_available(port):
                self._used_ports.add(port)
                return port
        
        raise RuntimeError("系统繁忙，无法分配端口")
```

### 3. 启动 ACP 进程

```python
async def _start_acp_process(self, port: int) -> bool:
    """启动 ACP 进程"""
    cmd = ["iflow", "--experimental-acp", "--stream", "--port", str(port)]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL
    )
    
    self._port_processes[port] = process
    
    # 等待进程就绪
    await asyncio.sleep(2.0)
    
    if process.returncode is not None:
        raise RuntimeError(f"ACP 进程启动失败")
    
    return True
```

### 4. 连接流程

```python
async def connect(self) -> None:
    """连接到 iFlow"""
    # 查找可用端口
    port = await self._find_available_port(self.user_id)
    
    # 启动 ACP 进程
    await self._start_acp_process(port)
    
    # 端口入栈
    if self.user_id not in self._user_ports:
        self._user_ports[self.user_id] = []
    self._user_ports[self.user_id].insert(0, port)  # 栈顶
    
    self._port = port
    self._url = f"ws://localhost:{port}/acp"
    
    # SDK 连接（不自动启动）
    self._options = IFlowOptions(
        url=self._url,
        auto_start_process=False,  # 关键！
        cwd=self.cwd,
        timeout=self.timeout,
        session_id=self.session_id,
    )
    
    # ... 连接逻辑
```

### 5. 断开逻辑

```python
async def _on_task_finish(self, user_id: int, port: int):
    """TaskFinishMessage 时的断开逻辑"""
    ports = self._user_ports.get(user_id, [])
    
    # 只有当栈里有多个端口，且当前端口不是栈顶时才断开
    if len(ports) > 1 and port != ports[0]:
        # 当前端口是旧的 ACP，断开它
        await self._stop_acp_process(port)
        ports.remove(port)
        self._used_ports.discard(port)

async def _stop_acp_process(self, port: int):
    """停止 ACP 进程"""
    process = self._port_processes.pop(port, None)
    if process and process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
```

---

## 场景测试

### 场景 1：用户首次连接
```
1. 分配端口 8091
2. 启动 ACP 进程
3. 端口栈：[8091]
4. TaskFinishMessage → 不变
```

### 场景 2：用户开第二个连接
```
1. 分配端口 8092
2. 启动新的 ACP 进程
3. 端口栈：[8092, 8091]
4. 旧连接 8091 输出完 TaskFinishMessage → 断开 8091
5. 端口栈：[8092]
```

### 场景 3：端口冲突
```
1. 端口 8091 被占用
2. 重试 → 尝试 8092
3. 成功 → 使用 8092
4. 重试 10 次仍失败 → 返回错误"系统繁忙"
```

---

## 优势

1. **流式输出**：手动启动带 `--stream` 的 ACP 进程
2. **资源管理**：端口可配置大范围，避免冲突
3. **平滑过渡**：旧连接输出完才断开，不影响用户体验
4. **错误处理**：端口分配失败有明确提示

## 注意事项

1. 端口范围要足够大，避免高并发时端口耗尽
2. 需要确保 iflow CLI 已安装并可在 PATH 中找到
3. 进程清理要彻底，避免僵尸进程
