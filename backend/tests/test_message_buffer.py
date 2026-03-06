"""
MessageBuffer 消息缓冲服务单元测试

测试目标：
- push 方法正确推送消息到用户队列
- consume 方法正确消费未读消息
- get_pending 方法正确获取待推送消息
- 消息过期机制正确工作
"""
import sys
import os

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import asyncio
from redis import asyncio as aioredis


# Redis 测试连接 URL
REDIS_URL = "redis://localhost:6379/0"


@pytest.fixture
async def redis_client():
    """创建 Redis 异步客户端"""
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield client
    # 清理：关闭连接
    await client.aclose()


@pytest.fixture
async def message_buffer():
    """创建 MessageBuffer 实例"""
    from services.message_buffer import MessageBuffer
    
    buffer = MessageBuffer(REDIS_URL)
    yield buffer
    
    # 清理：关闭连接
    await buffer.close()


@pytest.fixture
async def clean_redis(redis_client):
    """清理测试数据"""
    # 清理所有测试 key
    keys = await redis_client.keys("user:*:messages")
    if keys:
        await redis_client.delete(*keys)
    yield
    # 测试后清理
    keys = await redis_client.keys("user:*:messages")
    if keys:
        await redis_client.delete(*keys)


class TestMessageBufferPush:
    """测试 MessageBuffer push 方法"""

    @pytest.mark.asyncio
    async def test_push_creates_stream_entry(self, message_buffer, clean_redis):
        """测试 push 创建 Stream 条目"""
        message = {
            'type': 'stream',
            'content': 'Hello World',
            'is_delta': True
        }

        entry_id = await message_buffer.push(user_id=1, message=message)

        assert entry_id is not None
        assert isinstance(entry_id, str)

    @pytest.mark.asyncio
    async def test_push_stores_json_data(self, message_buffer, redis_client, clean_redis):
        """测试 push 存储 JSON 数据"""
        message = {
            'type': 'stream',
            'content': 'Test message',
            'is_delta': True
        }

        await message_buffer.push(user_id=2, message=message)

        # 验证 Stream 中有数据
        key = "user:2:messages"
        entries = await redis_client.xread({key: "0"}, count=1)

        assert len(entries) == 1
        assert entries[0][0] == key
        # 数据被 JSON 序列化存储
        data = entries[0][1][0][1]['data']
        parsed = json.loads(data)
        assert parsed['content'] == 'Test message'

    @pytest.mark.asyncio
    async def test_push_sets_ttl(self, message_buffer, redis_client, clean_redis):
        """测试 push 设置 TTL"""
        message = {'type': 'test', 'content': 'ttl test'}

        await message_buffer.push(user_id=3, message=message)

        key = "user:3:messages"
        ttl = await redis_client.ttl(key)

        # TTL 应该 > 0 且 <= 300 (5分钟)
        assert ttl > 0
        assert ttl <= 300


class TestMessageBufferConsume:
    """测试 MessageBuffer consume 方法"""

    @pytest.mark.asyncio
    async def test_consume_returns_messages(self, message_buffer, clean_redis):
        """测试 consume 返回消息"""
        # 先推送消息
        await message_buffer.push(user_id=10, message={'type': 'test', 'content': 'msg1'})
        await message_buffer.push(user_id=10, message={'type': 'test', 'content': 'msg2'})

        # 消费消息
        messages = await message_buffer.consume(user_id=10, count=10)

        assert messages is not None
        # xread 返回 [(stream_name, [entries...])]，所以消息数量是 len(messages[0][1])
        assert len(messages[0][1]) == 2

    @pytest.mark.asyncio
    async def test_consume_deletes_after_read(self, message_buffer, redis_client, clean_redis):
        """测试消费后删除消息"""
        await message_buffer.push(user_id=11, message={'type': 'test', 'content': 'msg'})

        # 第一次消费
        messages1 = await message_buffer.consume(user_id=11, count=10)
        assert len(messages1) == 1

        # 第二次消费应该为空
        messages2 = await message_buffer.consume(user_id=11, count=10)
        # xread 返回空列表或 None
        assert messages2 is None or len(messages2) == 0

    @pytest.mark.asyncio
    async def test_consume_respects_count(self, message_buffer, clean_redis):
        """测试 consume 限制数量"""
        # 推送 5 条消息
        for i in range(5):
            await message_buffer.push(user_id=12, message={'type': 'test', 'content': f'msg{i}'})

        # 只消费 2 条
        messages = await message_buffer.consume(user_id=12, count=2)

        # xread 返回 [(stream_name, [entries...])]，消息数量是 len(messages[0][1])
        assert len(messages[0][1]) == 2

    @pytest.mark.asyncio
    async def test_consume_empty_stream(self, message_buffer, clean_redis):
        """测试消费空 Stream"""
        messages = await message_buffer.consume(user_id=999, count=10)

        # 空 Stream 返回 None 或空列表
        assert messages is None or len(messages) == 0


class TestMessageBufferGetPending:
    """测试 MessageBuffer get_pending 方法"""

    @pytest.mark.asyncio
    async def test_get_pending_returns_unconsumed(self, message_buffer, clean_redis):
        """测试 get_pending 返回未消费消息"""
        await message_buffer.push(user_id=20, message={'type': 'test', 'content': 'pending1'})
        await message_buffer.push(user_id=20, message={'type': 'test', 'content': 'pending2'})

        pending = await message_buffer.get_pending(user_id=20)

        assert pending is not None
        # xread 返回 [(stream_name, [entries...])]，消息数量是 len(pending[0][1])
        assert len(pending[0][1]) == 2

    @pytest.mark.asyncio
    async def test_get_pending_does_not_delete(self, message_buffer, clean_redis):
        """测试 get_pending 不删除消息"""
        await message_buffer.push(user_id=21, message={'type': 'test', 'content': 'msg'})

        # 第一次获取
        pending1 = await message_buffer.get_pending(user_id=21)
        assert len(pending1) == 1

        # 第二次获取应该还有数据
        pending2 = await message_buffer.get_pending(user_id=21)
        assert len(pending2) == 1

    @pytest.mark.asyncio
    async def test_get_pending_respects_count_limit(self, message_buffer, clean_redis):
        """测试 get_pending 限制数量"""
        for i in range(10):
            await message_buffer.push(user_id=22, message={'type': 'test', 'content': f'msg{i}'})

        # 获取最多 50 条
        pending = await message_buffer.get_pending(user_id=22)

        # 默认 count=50，所以应该返回 10 条
        # xread 返回 [(stream_name, [entries...])]，消息数量是 len(pending[0][1])
        assert len(pending[0][1]) == 10

    @pytest.mark.asyncio
    async def test_get_pending_empty_stream(self, message_buffer, clean_redis):
        """测试获取空 Stream 的待推送消息"""
        pending = await message_buffer.get_pending(user_id=888)

        # 空 Stream 返回 None 或空列表
        assert pending is None or len(pending) == 0


class TestMessageBufferConnection:
    """测试 MessageBuffer 连接管理"""

    @pytest.mark.asyncio
    async def test_close_disconnects_redis(self, message_buffer):
        """测试 close 断开 Redis 连接"""
        # 先执行一个操作确保连接建立
        await message_buffer.push(user_id=99, message={'type': 'test'})

        # 关闭连接
        await message_buffer.close()

        # 验证连接已关闭（尝试操作应该失败或重新连接）
        # 这里只验证 close 不抛出异常
        assert True

    @pytest.mark.asyncio
    async def test_multiple_operations_same_connection(self, message_buffer, clean_redis):
        """测试同一连接执行多个操作"""
        # 多次 push
        for i in range(3):
            await message_buffer.push(user_id=30, message={'type': 'test', 'content': f'msg{i}'})

        # get_pending
        pending = await message_buffer.get_pending(user_id=30)
        # xread 返回 [(stream_name, [entries...])]，消息数量是 len(pending[0][1])
        assert len(pending[0][1]) == 3

        # consume
        messages = await message_buffer.consume(user_id=30, count=3)
        assert len(messages[0][1]) == 3


class TestMessageBufferEdgeCases:
    """测试边缘情况"""

    @pytest.mark.asyncio
    async def test_push_large_message(self, message_buffer, clean_redis):
        """测试推送大消息"""
        # 创建一个较大的消息
        large_content = "x" * 10000
        message = {
            'type': 'stream',
            'content': large_content,
            'is_delta': True
        }

        entry_id = await message_buffer.push(user_id=40, message=message)
        assert entry_id is not None

    @pytest.mark.asyncio
    async def test_push_unicode_content(self, message_buffer, clean_redis):
        """测试推送 Unicode 内容"""
        message = {
            'type': 'stream',
            'content': '你好世界 🌍 Hello World',
            'is_delta': True
        }

        entry_id = await message_buffer.push(user_id=41, message=message)
        assert entry_id is not None

        # 验证内容正确
        pending = await message_buffer.get_pending(user_id=41)
        data = json.loads(pending[0][1][0][1]['data'])
        assert data['content'] == '你好世界 🌍 Hello World'

    @pytest.mark.asyncio
    async def test_push_special_characters(self, message_buffer, clean_redis):
        """测试推送特殊字符"""
        message = {
            'type': 'stream',
            'content': '{"key": "value", "nested": {"a": 1}}',
            'is_delta': True
        }

        entry_id = await message_buffer.push(user_id=42, message=message)
        assert entry_id is not None
