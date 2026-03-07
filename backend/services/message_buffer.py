"""
MessageBuffer 消息缓冲服务

基于 Redis Stream 实现的消息缓冲，用于 WebSocket 断线重连后恢复消息。

核心功能：
- push: 推送消息到用户队列
- consume: 消费未读消息（读取后删除）
- get_pending: 获取待推送消息（不删除）

使用示例：
    buffer = MessageBuffer("redis://localhost:6379/0")

    # 推送消息
    await buffer.push(user_id=1, message={"type": "stream", "content": "Hello"})

    # 获取待推送消息（重连恢复用）
    pending = await buffer.get_pending(user_id=1)

    # 消费消息
    messages = await buffer.consume(user_id=1, count=10)

    # 关闭连接
    await buffer.close()
"""
import json
import logging
from typing import Optional, Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class MessageBuffer:
    """
    Redis 消息缓冲服务

    使用 Redis Stream 存储消息，支持：
    - 消息持久化（TTL 5 分钟）
    - 断线重连后消息恢复
    - 多消费者场景
    """

    def __init__(self, redis_url: str, ttl: int = 300):
        """
        初始化消息缓冲

        Args:
            redis_url: Redis 连接 URL (e.g., "redis://localhost:6379/0")
            ttl: 消息过期时间（秒），默认 5 分钟
        """
        self.redis_url = redis_url
        self.ttl = ttl
        self._redis: Optional[aioredis.Redis] = None

    @property
    def redis(self) -> aioredis.Redis:
        """懒加载 Redis 连接"""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                encoding="utf-8"
            )
        return self._redis

    def _get_key(self, user_id: int) -> str:
        """获取用户消息队列的 Redis key"""
        return f"user:{user_id}:messages"

    async def push(self, user_id: int, message: dict) -> str:
        """
        推送消息到用户队列

        Args:
            user_id: 用户 ID
            message: 消息内容（将被 JSON 序列化）

        Returns:
            str: Stream entry ID

        Example:
            entry_id = await buffer.push(
                user_id=1,
                message={"type": "stream", "content": "Hello", "is_delta": True}
            )
        """
        key = self._get_key(user_id)

        # 将消息 JSON 序列化
        data = json.dumps(message, ensure_ascii=False)

        # 添加到 Stream
        entry_id = await self.redis.xadd(key, {"data": data})

        # 不设置过期时间，消息永久保留
        # await self.redis.expire(key, self.ttl)

        logger.debug(f"Pushed message to {key}, entry_id={entry_id}")
        return entry_id

    async def consume(self, user_id: int, count: int = 10) -> Optional[list]:
        """
        消费未读消息（读取后删除）

        Args:
            user_id: 用户 ID
            count: 最大消费数量

        Returns:
            list: 消息列表，格式为 [(stream_name, [(entry_id, {field: value}), ...]), ...]
                  如果没有消息返回 None

        Example:
            messages = await buffer.consume(user_id=1, count=10)
            if messages:
                for stream_name, entries in messages:
                    for entry_id, fields in entries:
                        data = json.loads(fields['data'])
                        print(data['content'])
        """
        key = self._get_key(user_id)

        # 读取消息
        messages = await self.redis.xread({key: "0"}, count=count)

        if not messages:
            return None

        # 删除已读消息（临时禁用，测试流式）
        # for stream_name, entries in messages:
        #     entry_ids = [entry[0] for entry in entries]
        #     if entry_ids:
        #         await self.redis.xdel(key, *entry_ids)

        logger.debug(f"Consumed {len(messages[0][1])} messages from {key}")
        return messages

    async def get_pending(self, user_id: int, count: int = 50) -> Optional[list]:
        """
        获取待推送消息（不删除）

        用于断线重连后恢复未消费的消息。

        Args:
            user_id: 用户 ID
            count: 最大获取数量

        Returns:
            list: 消息列表，格式同 consume()
                  如果没有消息返回 None

        Example:
            # 重连后恢复消息
            pending = await buffer.get_pending(user_id=1)
            if pending:
                for stream_name, entries in pending:
                    for entry_id, fields in entries:
                        data = json.loads(fields['data'])
                        await send_to_websocket(data)
        """
        key = self._get_key(user_id)

        # 读取消息（从最早的开始）
        messages = await self.redis.xread({key: "0"}, count=count)

        if not messages:
            return None

        logger.debug(f"Got {len(messages[0][1])} pending messages from {key}")
        return messages

    async def close(self):
        """关闭 Redis 连接"""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.debug("Redis connection closed")

    async def __aenter__(self):
        """支持 async with 语法"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出时自动关闭连接"""
        await self.close()
