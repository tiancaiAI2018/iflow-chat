# Redis + EventBus 消息解耦方案

## 背景问题

移动端 WebSocket 连接不稳定，切屏时经常断开，导致 AI 输出内容丢失。

## 架构设计

### 整体流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              输入层 (Input Handlers)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   WebSocket 输入     ─────┐                                                  │
│                              │                                                │
│   (未来) HTTP API    ─────┼──→  EventBus.emit('user_message', data)        │
│                              │                                                │
│   (未来) MQTT       ─────┘                                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           业务处理层 (Business Logic)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   EventBus.on('user_message') → iFlow Client → 流式响应                    │
│                                          │                                   │
│                                          ▼                                   │
│                              EventBus.emit('ai_response', chunk)           │
│                              EventBus.emit('ai_complete', full_response)   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              输出层 (Output Handlers)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Redis Publisher   ←── EventBus.on('ai_response')  ←── 流式 chunks       │
│         │                        │                                           │
│         │                        └── EventBus.on('ai_complete')             │
│         │                              │                                     │
│         │                              ▼                                     │
│         │                         DB 存储完整响应                            │
│         │                                                                    │
│         ▼                                                                    │
│   Redis Stream: user:{user_id}:messages                                     │
│         │                                                                    │
│         ▼                                                                    │
│   WebSocket 订阅 Redis → 推送给前端                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Redis 安装部署

### 1. 版本选择

| 项目 | 版本 | 说明 |
|------|------|------|
| Redis Server | **7.2.x** | 当前稳定版，性能优化好，内存占用低 |
| Python 客户端 | `redis[asyncio] >= 5.0.0` | 支持异步操作 |
| blinker | `>= 1.7.0` | Flask 同款信号库，轻量稳定 |

### 2. 安装步骤

#### 2.1 安装 Redis Server

```bash
# 方式一：yum 安装（OpenCloudOS 兼容）
sudo yum install redis -y

# 方式二：源码编译（推荐，版本更新）
cd /tmp
wget https://download.redis.io/releases/redis-7.2.4.tar.gz
tar xzf redis-7.2.4.tar.gz
cd redis-7.2.4
make
sudo make install PREFIX=/usr/local/redis
```

#### 2.2 创建配置文件

```bash
sudo mkdir -p /etc/redis
sudo mkdir -p /var/lib/redis
sudo mkdir -p /var/log/redis

# 创建配置文件
sudo tee /etc/redis/redis.conf << 'EOF'
# 基础配置
bind 127.0.0.1
port 6379
daemonize yes
pidfile /var/run/redis/redis-server.pid
logfile /var/log/redis/redis.log
dir /var/lib/redis

# 内存限制（关键！）
maxmemory 32mb
maxmemory-policy allkeys-lru

# 持久化（可选，断电不丢数据）
# appendonly yes
# appendfsync everysec

# 性能优化
tcp-backlog 511
timeout 0
tcp-keepalive 300

# 安全（可选，生产环境建议设置密码）
# requirepass your_strong_password_here
EOF
```

#### 2.3 创建 systemd 服务

```bash
sudo tee /etc/systemd/system/redis.service << 'EOF'
[Unit]
Description=Redis In-Memory Data Store
After=network.target

[Service]
Type=forking
ExecStart=/usr/bin/redis-server /etc/redis/redis.conf
ExecStop=/usr/bin/redis-cli shutdown
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

# 重载 systemd
sudo systemctl daemon-reload

# 启动并设置开机自启
sudo systemctl start redis
sudo systemctl enable redis

# 验证
redis-cli ping  # 应返回 PONG
```

#### 2.4 安装 Python 依赖

```bash
cd /root/.iflow-bot/workspace/mybot/backend
pip install "redis[asyncio]>=5.0.0" "blinker>=1.7.0"
```

### 3. 部署后验证

```bash
# 检查服务状态
sudo systemctl status redis

# 检查内存配置
redis-cli CONFIG GET maxmemory

# 检查内存淘汰策略
redis-cli CONFIG GET maxmemory-policy

# 测试基本操作
redis-cli SET test_key "hello"
redis-cli GET test_key
redis-cli DEL test_key
```

### 4. 资源占用预估

| 指标 | 预估值 | 说明 |
|------|--------|------|
| 进程内存 | ~8-12 MB | 空闲状态 |
| 数据内存 | ≤32 MB | 受 maxmemory 限制 |
| 总内存 | ~40-45 MB | 进程 + 数据 |
| CPU | < 1% | 空闲时几乎为 0 |
| 磁盘 | < 1 MB | 无持久化时 |

### 5. 运维命令

```bash
# 查看内存使用
redis-cli INFO memory

# 查看当前连接数
redis-cli INFO clients

# 查看所有 key
redis-cli KEYS "*"

# 清空所有数据（慎用）
redis-cli FLUSHALL

# 监控实时命令
redis-cli MONITOR

# 查看日志
tail -f /var/log/redis/redis.log
```

---

## 核心组件设计

### 1. EventBus (使用 blinker)

```python
# services/event_bus.py
from blinker import Signal

class EventBus:
    # 信号定义
    user_message = Signal('user_message')      # 用户输入
    ai_response = Signal('ai_response')        # AI 流式响应
    ai_complete = Signal('ai_complete')        # AI 响应完成
    
    @classmethod
    def emit(cls, signal_name: str, sender=None, **kwargs):
        """发射信号"""
        signal = getattr(cls, signal_name)
        signal.send(sender, **kwargs)
    
    @classmethod
    def on(cls, signal_name: str):
        """订阅信号装饰器"""
        signal = getattr(cls, signal_name)
        return signal.connect
```

### 2. Redis 配置（轻量级）

```python
# config.py 新增
REDIS_URL = "redis://localhost:6379/0"
REDIS_MAX_MEMORY = "32mb"        # 限制最大内存
REDIS_MESSAGE_TTL = 300          # 消息保留 5 分钟
```

### 3. 消息缓冲服务

```python
# services/message_buffer.py
import redis.asyncio as redis
import json

class MessageBuffer:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
    
    async def push(self, user_id: int, message: dict):
        """推送消息到用户队列"""
        key = f"user:{user_id}:messages"
        await self.redis.xadd(key, {"data": json.dumps(message)})
        await self.redis.expire(key, 300)  # 5分钟过期
    
    async def consume(self, user_id: int, count: int = 10):
        """消费未读消息"""
        key = f"user:{user_id}:messages"
        messages = await self.redis.xread({key: "0"}, count=count)
        if messages:
            # 返回消息并删除
            ids = [msg[0] for msg in messages[0][1]]
            await self.redis.xdel(key, *ids)
        return messages
    
    async def get_pending(self, user_id: int):
        """获取待推送消息（重连恢复用）"""
        key = f"user:{user_id}:messages"
        return await self.redis.xread({key: "0"}, count=50)
```

### 4. 输入输出组件解耦

```python
# services/input_handlers/websocket_input.py
class WebSocketInputHandler:
    """WebSocket 输入处理器"""
    
    def __init__(self):
        EventBus.user_message.connect(self._on_user_message)
    
    async def handle(self, user_id: int, content: str, conversation_id: int):
        # 只负责发射事件，不关心后续处理
        EventBus.emit('user_message', user_id=user_id, 
                     content=content, conversation_id=conversation_id)


# services/output_handlers/redis_output.py
class RedisOutputHandler:
    """Redis 输出处理器"""
    
    def __init__(self, buffer: MessageBuffer):
        self.buffer = buffer
        # 订阅 AI 响应事件
        EventBus.ai_response.connect(self._on_ai_response)
        EventBus.ai_complete.connect(self._on_ai_complete)
    
    async def _on_ai_response(self, sender, **kwargs):
        """流式推送"""
        await self.buffer.push(kwargs['user_id'], {
            'type': 'stream',
            'content': kwargs['content'],
            'is_delta': True
        })
    
    async def _on_ai_complete(self, sender, **kwargs):
        """完成后存 DB + 推送完成标记"""
        # 存储到数据库
        await save_to_db(kwargs)
        # 推送完成标记
        await self.buffer.push(kwargs['user_id'], {
            'type': 'complete',
            'content': kwargs['content']
        })
```

---

## 文件改动清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/requirements.txt` | 修改 | 添加 `redis`、`blinker` |
| `backend/config.py` | 修改 | 添加 Redis 配置 |
| `backend/services/event_bus.py` | 新建 | EventBus 信号定义 |
| `backend/services/message_buffer.py` | 新建 | Redis 消息缓冲 |
| `backend/services/input_handlers/__init__.py` | 新建 | 输入处理器模块 |
| `backend/services/input_handlers/websocket_input.py` | 新建 | WebSocket 输入适配器 |
| `backend/services/output_handlers/__init__.py` | 新建 | 输出处理器模块 |
| `backend/services/output_handlers/redis_output.py` | 新建 | Redis 输出适配器 |
| `backend/services/output_handlers/db_output.py` | 新建 | 数据库输出适配器 |
| `backend/routers/websocket.py` | 修改 | 接入 EventBus |
| `backend/main.py` | 修改 | 初始化 Redis 连接 |
| `frontend/src/contexts/ChatContext.tsx` | 修改 | 重连后从 Redis 拉取消息 |

---

## 实施步骤

### Phase 1: Redis 安装部署
- [ ] 安装 Redis Server（yum 或源码编译）
- [ ] 创建配置文件 `/etc/redis/redis.conf`
- [ ] 配置 systemd 服务，开机自启
- [ ] 安装 Python 依赖：`redis[asyncio]`、`blinker`

### Phase 2: 后端核心模块
- [ ] 创建 `services/event_bus.py` - EventBus 信号定义
- [ ] 创建 `services/message_buffer.py` - Redis 消息缓冲
- [ ] 修改 `config.py` - 添加 Redis 配置
- [ ] 修改 `requirements.txt` - 添加依赖

### Phase 3: 输入输出处理器
- [ ] 创建 `services/input_handlers/__init__.py`
- [ ] 创建 `services/input_handlers/websocket_input.py`
- [ ] 创建 `services/output_handlers/__init__.py`
- [ ] 创建 `services/output_handlers/redis_output.py`
- [ ] 创建 `services/output_handlers/db_output.py`

### Phase 4: 集成改造
- [ ] 修改 `routers/websocket.py` - 接入 EventBus
- [ ] 修改 `main.py` - 初始化 Redis 连接和处理器

### Phase 5: 前端改造
- [ ] 修改 `ChatContext.tsx` - 重连后从 Redis 拉取消息
- [ ] 添加 API 接口调用获取待消费消息

### Phase 6: 测试验证
- [ ] 单元测试：EventBus、MessageBuffer
- [ ] 集成测试：断线重连场景
- [ ] 压力测试：并发消息处理

---

## 优势总结

1. **解耦彻底**：输入输出组件可独立替换
2. **资源可控**：Redis 内存受限 + 自动过期
3. **扩展性好**：未来可添加 HTTP 输入、MQTT 输出等
4. **断线恢复**：重连后从 Redis 拉取未消费消息