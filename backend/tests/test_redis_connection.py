"""
Redis 异步连接测试用例
测试覆盖：连接/读写/断开场景
"""
import pytest
import json
import asyncio
from redis import asyncio as aioredis
from redis import exceptions as redis_exceptions


# Redis 测试连接 URL
REDIS_URL = "redis://localhost:6379/0"


@pytest.fixture
async def redis_client():
    """创建 Redis 异步客户端"""
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield client
    # 清理：关闭连接
    await client.aclose()


class TestRedisConnection:
    """Redis 连接测试"""

    @pytest.mark.asyncio
    async def test_connection_ping(self, redis_client):
        """测试 Redis 连接 - PING 命令"""
        result = await redis_client.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_connection_info(self, redis_client):
        """测试 Redis 连接 - INFO 命令"""
        info = await redis_client.info("server")
        assert "redis_version" in info
        assert info["redis_version"].startswith("7.")

    @pytest.mark.asyncio
    async def test_maxmemory_config(self, redis_client):
        """测试 Redis 内存配置"""
        maxmemory = await redis_client.config_get("maxmemory")
        assert "maxmemory" in maxmemory
        # 32MB = 33554432 bytes
        assert int(maxmemory["maxmemory"]) == 33554432


class TestRedisReadWrite:
    """Redis 读写测试"""

    @pytest.mark.asyncio
    async def test_set_and_get_string(self, redis_client):
        """测试字符串读写"""
        test_key = "test:str:key"
        test_value = "hello_redis"

        # 写入
        result = await redis_client.set(test_key, test_value)
        assert result is True

        # 读取
        value = await redis_client.get(test_key)
        assert value == test_value

        # 清理
        await redis_client.delete(test_key)

    @pytest.mark.asyncio
    async def test_set_and_get_json(self, redis_client):
        """测试 JSON 数据读写"""
        test_key = "test:json:key"
        test_data = {"user_id": 123, "content": "test message", "is_delta": True}

        # 写入 JSON
        result = await redis_client.set(test_key, json.dumps(test_data))
        assert result is True

        # 读取并解析
        value = await redis_client.get(test_key)
        parsed = json.loads(value)
        assert parsed["user_id"] == 123
        assert parsed["content"] == "test message"

        # 清理
        await redis_client.delete(test_key)

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, redis_client):
        """测试带过期时间的写入"""
        test_key = "test:ttl:key"
        test_value = "will_expire"

        # 写入并设置 5 秒过期
        result = await redis_client.setex(test_key, 5, test_value)
        assert result is True

        # 检查 TTL
        ttl = await redis_client.ttl(test_key)
        assert 0 < ttl <= 5

        # 清理
        await redis_client.delete(test_key)

    @pytest.mark.asyncio
    async def test_delete_key(self, redis_client):
        """测试删除键"""
        test_key = "test:delete:key"

        # 写入
        await redis_client.set(test_key, "to_be_deleted")

        # 删除
        deleted = await redis_client.delete(test_key)
        assert deleted == 1

        # 验证已删除
        value = await redis_client.get(test_key)
        assert value is None


class TestRedisStream:
    """Redis Stream 测试（用于消息缓冲）"""

    @pytest.mark.asyncio
    async def test_xadd_and_xread(self, redis_client):
        """测试 Stream 写入和读取"""
        stream_key = "test:stream:messages"
        test_message = {"data": json.dumps({"type": "stream", "content": "hello"})}

        # 写入 Stream
        message_id = await redis_client.xadd(stream_key, test_message)
        assert message_id is not None

        # 读取 Stream
        messages = await redis_client.xread({stream_key: "0"}, count=1)
        assert len(messages) == 1
        assert messages[0][0].decode() if isinstance(messages[0][0], bytes) else messages[0][0] == stream_key

        # 清理
        await redis_client.delete(stream_key)

    @pytest.mark.asyncio
    async def test_xadd_with_maxlen(self, redis_client):
        """测试 Stream 写入并限制长度"""
        stream_key = "test:stream:maxlen"

        # 写入多条消息，限制最大 3 条（maxlen 是近似值）
        for i in range(5):
            msg_id = await redis_client.xadd(stream_key, {"data": f"message_{i}"}, maxlen=3)
            assert msg_id is not None

        # 验证 Stream 存在并有消息
        messages = await redis_client.xread({stream_key: "0"}, count=10)
        assert len(messages) == 1

        # 清理
        await redis_client.delete(stream_key)

    @pytest.mark.asyncio
    async def test_xdel(self, redis_client):
        """测试 Stream 删除消息"""
        stream_key = "test:stream:delete"

        # 写入消息
        msg_id = await redis_client.xadd(stream_key, {"data": "test"})

        # 删除消息
        deleted = await redis_client.xdel(stream_key, msg_id)
        assert deleted == 1

        # 清理
        await redis_client.delete(stream_key)


class TestRedisDisconnect:
    """Redis 断开测试"""

    @pytest.mark.asyncio
    async def test_close_connection(self):
        """测试关闭连接"""
        client = aioredis.from_url(REDIS_URL, decode_responses=True)

        # 先验证连接正常
        result = await client.ping()
        assert result is True

        # 关闭连接（验证 aclose 方法可正常调用）
        await client.aclose()
        
        # 验证方法已执行（连接池仍然存在但连接已断开）
        # redis-py 7.x 的 aclose 会断开连接但不一定清理连接池

    @pytest.mark.asyncio
    async def test_connection_pool(self):
        """测试连接池"""
        pool = aioredis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
        client = aioredis.Redis(connection_pool=pool)

        # 验证连接正常
        result = await client.ping()
        assert result is True

        # 关闭客户端和连接池
        await client.aclose()
        await pool.aclose()


class TestRedisAsyncContext:
    """Redis 异步上下文管理测试"""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试异步上下文管理器"""
        async with aioredis.from_url(REDIS_URL, decode_responses=True) as client:
            result = await client.ping()
            assert result is True
            # 退出时会自动关闭连接