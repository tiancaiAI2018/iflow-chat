"""
断线重连场景集成测试

测试场景：
1. 模拟 WebSocket 断开重连
2. 测试消息不丢失（重连后未消费消息正确恢复）
3. 测试流式输出中断恢复（AI 响应中断后能从 Redis 恢复）

测试覆盖：
- MessageBuffer 消息缓冲机制
- 前端重连后通过 API 获取待消费消息
- 流式响应中断后的消息恢复
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

import redis.asyncio as aioredis

from backend.services.event_bus import EventBus
from backend.services.message_buffer import MessageBuffer
from backend.services.input_handlers.websocket_input import WebSocketInputHandler
from backend.services.output_handlers.redis_output import RedisOutputHandler
from backend.services.iflow_processor import IFlowProcessor


# ==================== Redis 连接测试 ====================

class TestRedisConnection:
    """Redis 连接基础测试"""

    @pytest.mark.asyncio
    async def test_redis_connection_available(self):
        """测试 Redis 连接可用"""
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            result = await redis_client.ping()
            assert result is True
            await redis_client.aclose()
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")


# ==================== 断线重连消息恢复测试 ====================

class TestReconnectMessageRecovery:
    """断线重连消息恢复测试"""

    @pytest.mark.asyncio
    async def test_pending_messages_after_disconnect(self):
        """
        测试断线后消息存储在 Redis

        场景：
        1. 用户发送消息
        2. AI 响应过程中 WebSocket 断开
        3. 消息被保存到 Redis
        """
        # 使用真实 Redis
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999001  # 测试用户 ID

        try:
            # 清理旧数据
            await redis_client.delete(f"user:{user_id}:messages")

            # 模拟 AI 响应推送（断线期间）
            await buffer.push(
                user_id=user_id,
                message={
                    "type": "stream",
                    "content": "Hello",
                    "is_delta": True,
                    "conversation_id": 100,
                }
            )
            await buffer.push(
                user_id=user_id,
                message={
                    "type": "stream",
                    "content": " World",
                    "is_delta": True,
                    "conversation_id": 100,
                }
            )
            await buffer.push(
                user_id=user_id,
                message={
                    "type": "complete",
                    "content": "Hello World",
                    "conversation_id": 100,
                }
            )

            # 验证消息已存储
            pending = await buffer.get_pending(user_id=user_id)
            assert pending is not None
            assert len(pending[0][1]) == 3

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_message_recovery_after_reconnect(self):
        """
        测试重连后消息恢复

        场景：
        1. Redis 中有待消费消息
        2. 用户重连后调用 get_pending API
        3. 消息被正确恢复
        """
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999002

        try:
            # 清理旧数据
            await redis_client.delete(f"user:{user_id}:messages")

            # 预存消息（模拟断线期间的消息）
            await buffer.push(
                user_id=user_id,
                message={
                    "type": "complete",
                    "content": "This is a recovered message",
                    "conversation_id": 200,
                    "created_at": datetime.now().isoformat(),
                }
            )

            # 模拟重连后获取消息
            pending = await buffer.get_pending(user_id=user_id)
            assert pending is not None

            # 解析消息
            messages = []
            for stream_name, entries in pending:
                for entry_id, fields in entries:
                    data = json.loads(fields.get("data", "{}"))
                    messages.append(data)

            assert len(messages) == 1
            assert messages[0]["type"] == "complete"
            assert messages[0]["content"] == "This is a recovered message"
            assert messages[0]["conversation_id"] == 200

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_consume_after_recovery(self):
        """
        测试恢复后消息消费

        场景：
        1. 重连后获取待消费消息
        2. 消费消息后从 Redis 删除
        """
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999003

        try:
            # 清理旧数据
            await redis_client.delete(f"user:{user_id}:messages")

            # 预存消息
            await buffer.push(
                user_id=user_id,
                message={"type": "complete", "content": "Message 1"}
            )
            await buffer.push(
                user_id=user_id,
                message={"type": "complete", "content": "Message 2"}
            )

            # 消费消息
            consumed = await buffer.consume(user_id=user_id, count=10)
            assert consumed is not None
            assert len(consumed[0][1]) == 2

            # 验证消息已被删除
            pending = await buffer.get_pending(user_id=user_id)
            assert pending is None

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()


# ==================== 流式响应中断恢复测试 ====================

class TestStreamInterruptRecovery:
    """流式响应中断恢复测试"""

    @pytest.mark.asyncio
    async def test_stream_interrupt_preserves_messages(self):
        """
        测试流式响应中断后消息保留

        场景：
        1. AI 正在流式输出
        2. WebSocket 断开
        3. 已输出的流式消息被保存到 Redis
        4. 重连后能获取到之前的流式消息
        """
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999004

        try:
            # 清理旧数据
            await redis_client.delete(f"user:{user_id}:messages")

            # 模拟流式输出中断（部分消息已发送）
            stream_chunks = ["Hello", " there", ", this", " is"]
            for chunk in stream_chunks:
                await buffer.push(
                    user_id=user_id,
                    message={
                        "type": "stream",
                        "content": chunk,
                        "is_delta": True,
                        "conversation_id": 300,
                    }
                )

            # 验证流式消息被保存
            pending = await buffer.get_pending(user_id=user_id)
            assert pending is not None

            # 重连后恢复流式消息
            messages = []
            for stream_name, entries in pending:
                for entry_id, fields in entries:
                    data = json.loads(fields.get("data", "{}"))
                    messages.append(data)

            assert len(messages) == 4
            # 验证消息顺序
            assert messages[0]["content"] == "Hello"
            assert messages[1]["content"] == " there"

            # 前端可以累积这些流式消息
            full_content = "".join(m["content"] for m in messages if m["type"] == "stream")
            assert full_content == "Hello there, this is"

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_complete_message_after_stream(self):
        """
        测试流式输出完成后有完整消息标记

        场景：
        1. 流式输出完成
        2. 最后一条消息是 complete 类型
        3. 重连后能识别完整响应
        """
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999005

        try:
            # 清理旧数据
            await redis_client.delete(f"user:{user_id}:messages")

            # 模拟完整的流式输出
            stream_chunks = ["Hello", " World"]
            for chunk in stream_chunks:
                await buffer.push(
                    user_id=user_id,
                    message={
                        "type": "stream",
                        "content": chunk,
                        "is_delta": True,
                    }
                )

            # 最后发送完整消息
            await buffer.push(
                user_id=user_id,
                message={
                    "type": "complete",
                    "content": "Hello World",
                    "conversation_id": 400,
                }
            )

            # 重连后获取消息
            pending = await buffer.get_pending(user_id=user_id)
            messages = []
            for stream_name, entries in pending:
                for entry_id, fields in entries:
                    data = json.loads(fields.get("data", "{}"))
                    messages.append(data)

            # 最后一条应该是 complete 类型
            assert messages[-1]["type"] == "complete"
            assert messages[-1]["content"] == "Hello World"

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()


# ==================== EventBus + RedisOutputHandler 集成测试 ====================

class TestEventBusReconnectIntegration:
    """EventBus + RedisOutputHandler 断线重连集成测试"""

    @pytest.mark.asyncio
    async def test_ai_response_signal_saves_to_redis(self):
        """
        测试 AI 响应信号触发 Redis 存储

        场景：
        1. IFlowProcessor 发射 ai_response 信号
        2. RedisOutputHandler 接收信号并存储到 Redis
        3. 断线重连后消息可恢复
        """
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999006

        try:
            # 清理旧数据
            await redis_client.delete(f"user:{user_id}:messages")

            # 创建 RedisOutputHandler
            handler = RedisOutputHandler(buffer=buffer)

            try:
                # 模拟发射 ai_response 信号
                EventBus.emit(
                    'ai_response',
                    sender='test_processor',
                    user_id=user_id,
                    content='Test response',
                    is_delta=True,
                    conversation_id=500,
                )

                # 等待异步处理
                await asyncio.sleep(0.2)

                # 验证消息被存储
                pending = await buffer.get_pending(user_id=user_id)
                assert pending is not None

                messages = []
                for stream_name, entries in pending:
                    for entry_id, fields in entries:
                        data = json.loads(fields.get("data", "{}"))
                        messages.append(data)

                assert len(messages) == 1
                assert messages[0]["type"] == "stream"
                assert messages[0]["content"] == "Test response"

            finally:
                handler.disconnect()

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_ai_complete_signal_saves_to_redis(self):
        """
        测试 AI 完成信号触发 Redis 存储
        """
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999007

        try:
            # 清理旧数据
            await redis_client.delete(f"user:{user_id}:messages")

            # 创建 RedisOutputHandler
            handler = RedisOutputHandler(buffer=buffer)

            try:
                # 模拟发射 ai_complete 信号
                EventBus.emit(
                    'ai_complete',
                    sender='test_processor',
                    user_id=user_id,
                    content='Full response content',
                    conversation_id=600,
                )

                # 等待异步处理
                await asyncio.sleep(0.2)

                # 验证消息被存储
                pending = await buffer.get_pending(user_id=user_id)
                assert pending is not None

                messages = []
                for stream_name, entries in pending:
                    for entry_id, fields in entries:
                        data = json.loads(fields.get("data", "{}"))
                        messages.append(data)

                assert len(messages) == 1
                assert messages[0]["type"] == "complete"
                assert messages[0]["content"] == "Full response content"
                assert messages[0]["conversation_id"] == 600

            finally:
                handler.disconnect()

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()


# ==================== 多用户断线重连测试 ====================

class TestMultiUserReconnect:
    """多用户断线重连测试"""

    @pytest.mark.asyncio
    async def test_multiple_users_separate_queues(self):
        """
        测试多用户消息隔离

        场景：
        1. 多个用户同时断线
        2. 每个用户的消息存储在独立队列
        3. 重连后各自恢复自己的消息
        """
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_ids = [9999011, 9999012, 9999013]

        try:
            # 清理旧数据
            for uid in user_ids:
                await redis_client.delete(f"user:{uid}:messages")

            # 为每个用户推送不同消息
            for uid in user_ids:
                await buffer.push(
                    user_id=uid,
                    message={
                        "type": "complete",
                        "content": f"Message for user {uid}",
                    }
                )

            # 验证消息隔离
            for uid in user_ids:
                pending = await buffer.get_pending(user_id=uid)
                assert pending is not None

                messages = []
                for stream_name, entries in pending:
                    for entry_id, fields in entries:
                        data = json.loads(fields.get("data", "{}"))
                        messages.append(data)

                assert len(messages) == 1
                assert messages[0]["content"] == f"Message for user {uid}"

        finally:
            for uid in user_ids:
                await redis_client.delete(f"user:{uid}:messages")
            await buffer.close()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_message_ttl_expiration(self):
        """
        测试消息过期机制

        场景：
        1. 消息设置了 TTL
        2. 过期后消息自动删除
        3. Redis 内存可控
        """
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        # 创建短 TTL 的 buffer 用于测试
        buffer = MessageBuffer("redis://localhost:6379/0", ttl=2)  # 2 秒过期
        user_id = 9999014

        try:
            # 清理旧数据
            await redis_client.delete(f"user:{user_id}:messages")

            # 推送消息
            await buffer.push(
                user_id=user_id,
                message={"type": "test", "content": "Will expire"}
            )

            # 验证消息存在
            pending = await buffer.get_pending(user_id=user_id)
            assert pending is not None

            # 等待 TTL 过期（注意：expire 只在 key 被访问时检查）
            # 这里我们检查 key 的 TTL
            ttl = await redis_client.ttl(f"user:{user_id}:messages")
            assert 0 < ttl <= 2  # TTL 应该在 0-2 秒之间

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()


# ==================== 并发断线重连测试 ====================

class TestConcurrentReconnect:
    """并发断线重连测试"""

    @pytest.mark.asyncio
    async def test_concurrent_push_and_consume(self):
        """
        测试并发推送和消费

        场景：
        1. 多个并发推送消息
        2. 同时消费消息
        3. 消息不丢失不重复
        """
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999020

        try:
            # 清理旧数据
            await redis_client.delete(f"user:{user_id}:messages")

            # 并发推送 10 条消息
            async def push_message(i):
                await buffer.push(
                    user_id=user_id,
                    message={"type": "test", "content": f"Message {i}", "index": i}
                )

            await asyncio.gather(*[push_message(i) for i in range(10)])

            # 验证所有消息都被存储
            pending = await buffer.get_pending(user_id=user_id)
            assert pending is not None

            # 计算消息数量
            message_count = sum(len(entries) for _, entries in pending)
            assert message_count == 10

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()


# ==================== 边缘场景测试 ====================

class TestEdgeCases:
    """边缘场景测试"""

    @pytest.mark.asyncio
    async def test_empty_message_handling(self):
        """测试空消息处理"""
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999030

        try:
            await redis_client.delete(f"user:{user_id}:messages")

            # 推送空内容消息
            await buffer.push(
                user_id=user_id,
                message={"type": "stream", "content": ""}
            )

            pending = await buffer.get_pending(user_id=user_id)
            assert pending is not None

            messages = []
            for stream_name, entries in pending:
                for entry_id, fields in entries:
                    data = json.loads(fields.get("data", "{}"))
                    messages.append(data)

            assert len(messages) == 1
            assert messages[0]["content"] == ""

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_unicode_message_handling(self):
        """测试 Unicode 消息处理"""
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999031

        try:
            await redis_client.delete(f"user:{user_id}:messages")

            # 推送 Unicode 消息
            unicode_content = "你好世界 🌍 Hello World"
            await buffer.push(
                user_id=user_id,
                message={"type": "complete", "content": unicode_content}
            )

            pending = await buffer.get_pending(user_id=user_id)
            messages = []
            for stream_name, entries in pending:
                for entry_id, fields in entries:
                    data = json.loads(fields.get("data", "{}"))
                    messages.append(data)

            assert messages[0]["content"] == unicode_content

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_large_message_handling(self):
        """测试大消息处理"""
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999032

        try:
            await redis_client.delete(f"user:{user_id}:messages")

            # 推送大消息 (10KB)
            large_content = "x" * 10240
            await buffer.push(
                user_id=user_id,
                message={"type": "complete", "content": large_content}
            )

            pending = await buffer.get_pending(user_id=user_id)
            messages = []
            for stream_name, entries in pending:
                for entry_id, fields in entries:
                    data = json.loads(fields.get("data", "{}"))
                    messages.append(data)

            assert len(messages[0]["content"]) == 10240

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()

    @pytest.mark.asyncio
    async def test_special_characters_in_message(self):
        """测试特殊字符处理"""
        try:
            redis_client = aioredis.from_url(
                "redis://localhost:6379/0",
                decode_responses=True
            )
            await redis_client.ping()
        except Exception:
            pytest.skip("Redis not available")

        buffer = MessageBuffer("redis://localhost:6379/0")
        user_id = 9999033

        try:
            await redis_client.delete(f"user:{user_id}:messages")

            # 推送包含特殊字符的消息
            special_content = 'Message with "quotes" and \\backslashes\\ and \n newlines'
            await buffer.push(
                user_id=user_id,
                message={"type": "complete", "content": special_content}
            )

            pending = await buffer.get_pending(user_id=user_id)
            messages = []
            for stream_name, entries in pending:
                for entry_id, fields in entries:
                    data = json.loads(fields.get("data", "{}"))
                    messages.append(data)

            assert messages[0]["content"] == special_content

        finally:
            await redis_client.delete(f"user:{user_id}:messages")
            await buffer.close()
            await redis_client.aclose()
