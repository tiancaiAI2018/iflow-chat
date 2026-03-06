#!/usr/bin/env python3
"""
并发压力测试：验证 Redis 消息缓冲在高并发场景下的表现

测试场景：
1. 模拟 10 个并发用户发送消息
2. 验证 Redis 内存限制生效（maxmemory 32mb）
3. 验证消息不丢失不重复
4. 生成测试报告显示吞吐量和延迟指标
"""
import asyncio
import json
import time
from typing import List, Dict, Any
import redis.asyncio as aioredis
from datetime import datetime

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.message_buffer import MessageBuffer
from config import settings


class StressTestReport:
    """压力测试报告"""

    def __init__(self):
        self.start_time: datetime = None
        self.end_time: datetime = None
        self.total_messages_sent: int = 0
        self.total_messages_consumed: int = 0
        self.total_messages_lost: int = 0
        self.total_messages_duplicate: int = 0
        self.throughput: float = 0.0  # 消息/秒
        self.avg_latency_ms: float = 0.0
        self.max_latency_ms: float = 0.0
        self.min_latency_ms: float = float('inf')
        self.redis_memory_used_mb: float = 0.0
        self.redis_memory_limit_mb: float = 0.0
        self.memory_limit_ok: bool = True
        self.user_stats: List[Dict[str, Any]] = []
        self.errors: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_time": {
                "start": self.start_time.isoformat() if self.start_time else None,
                "end": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0
            },
            "message_stats": {
                "total_sent": self.total_messages_sent,
                "total_consumed": self.total_messages_consumed,
                "total_lost": self.total_messages_lost,
                "total_duplicate": self.total_messages_duplicate,
                "loss_rate": f"{self.total_messages_lost / self.total_messages_sent * 100:.2f}%" if self.total_messages_sent > 0 else "0%",
                "duplicate_rate": f"{self.total_messages_duplicate / self.total_messages_sent * 100:.2f}%" if self.total_messages_sent > 0 else "0%"
            },
            "performance": {
                "throughput_msgs_per_sec": round(self.throughput, 2),
                "avg_latency_ms": round(self.avg_latency_ms, 2),
                "max_latency_ms": round(self.max_latency_ms, 2),
                "min_latency_ms": round(self.min_latency_ms, 2) if self.min_latency_ms != float('inf') else 0
            },
            "redis": {
                "memory_used_mb": round(self.redis_memory_used_mb, 2),
                "memory_limit_mb": round(self.redis_memory_limit_mb, 2),
                "memory_limit_ok": self.memory_limit_ok
            },
            "user_stats": self.user_stats,
            "errors": self.errors,
            "success": self.total_messages_lost == 0 and self.total_messages_duplicate == 0 and self.memory_limit_ok
        }


class ConcurrentStressTest:
    """并发压力测试"""

    def __init__(self, num_users: int = 10, messages_per_user: int = 100):
        self.num_users = num_users
        self.messages_per_user = messages_per_user
        self.redis_url = settings.REDIS_URL
        self.message_buffer = MessageBuffer(self.redis_url)
        self.redis: aioredis.Redis = None
        self.report = StressTestReport()
        self.latencies: List[float] = []
        self.message_ids: Dict[int, set] = {}  # user_id -> set of message_ids sent
        self.consumed_ids: Dict[int, set] = {}  # user_id -> set of message_ids consumed

    async def setup(self):
        """初始化测试环境"""
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
        
        # 清空之前的测试数据
        for user_id in range(1, self.num_users + 1):
            key = f"user:{user_id}:messages"
            await self.redis.delete(key)
        
        # 初始化追踪字典
        for user_id in range(1, self.num_users + 1):
            self.message_ids[user_id] = set()
            self.consumed_ids[user_id] = set()

    async def cleanup(self):
        """清理测试环境"""
        if self.message_buffer:
            await self.message_buffer.close()
        if self.redis:
            await self.redis.aclose()

    async def send_message(self, user_id: int, message_id: int) -> float:
        """
        发送单条消息并返回延迟
        
        Args:
            user_id: 用户 ID
            message_id: 消息 ID
            
        Returns:
            float: 延迟（毫秒）
        """
        start = time.time()
        
        message = {
            "type": "stream",
            "content": f"User {user_id} - Message {message_id} - Timestamp {time.time()}",
            "message_id": message_id,
            "user_id": user_id
        }
        
        await self.message_buffer.push(user_id, message)
        
        end = time.time()
        latency = (end - start) * 1000  # 毫秒
        
        self.message_ids[user_id].add(message_id)
        self.latencies.append(latency)
        
        return latency

    async def send_messages_for_user(self, user_id: int):
        """
        为单个用户发送所有消息
        
        Args:
            user_id: 用户 ID
        """
        user_start = time.time()
        
        for message_id in range(1, self.messages_per_user + 1):
            try:
                await self.send_message(user_id, message_id)
            except Exception as e:
                self.report.errors.append(f"User {user_id} failed to send message {message_id}: {str(e)}")
        
        user_end = time.time()
        user_duration = user_end - user_start
        
        self.report.user_stats.append({
            "user_id": user_id,
            "messages_sent": self.messages_per_user,
            "duration_seconds": round(user_duration, 2),
            "throughput": round(self.messages_per_user / user_duration, 2) if user_duration > 0 else 0
        })

    async def consume_messages_for_user(self, user_id: int):
        """
        为单个用户消费所有消息
        
        Args:
            user_id: 用户 ID
        """
        consumed_count = 0
        
        while True:
            try:
                messages = await self.message_buffer.consume(user_id, count=10)
                if not messages:
                    break
                
                for stream_name, entries in messages:
                    for entry_id, fields in entries:
                        data = json.loads(fields['data'])
                        message_id = data.get('message_id')
                        
                        # 检查重复
                        if message_id in self.consumed_ids[user_id]:
                            self.report.total_messages_duplicate += 1
                        else:
                            self.consumed_ids[user_id].add(message_id)
                            consumed_count += 1
            except Exception as e:
                self.report.errors.append(f"User {user_id} failed to consume messages: {str(e)}")
                break
        
        # 计算丢失的消息
        sent_ids = self.message_ids[user_id]
        consumed_ids = self.consumed_ids[user_id]
        lost_ids = sent_ids - consumed_ids
        
        if lost_ids:
            self.report.total_messages_lost += len(lost_ids)
            self.report.errors.append(f"User {user_id} lost {len(lost_ids)} messages: {sorted(list(lost_ids))[:10]}...")

    async def check_redis_memory(self):
        """检查 Redis 内存使用情况"""
        info = await self.redis.info('memory')
        self.report.redis_memory_used_mb = info['used_memory'] / 1024 / 1024
        
        # 获取 maxmemory 配置
        maxmemory = await self.redis.config_get('maxmemory')
        limit = int(maxmemory['maxmemory'])
        self.report.redis_memory_limit_mb = limit / 1024 / 1024 if limit > 0 else 0
        
        # 验证内存限制
        if limit > 0 and info['used_memory'] > limit:
            self.report.memory_limit_ok = False
            self.report.errors.append(f"Redis memory ({info['used_memory'] / 1024 / 1024:.2f} MB) exceeds limit ({limit / 1024 / 1024:.2f} MB)")

    async def run(self):
        """运行压力测试"""
        print(f"\n{'='*80}")
        print(f"并发压力测试开始")
        print(f"{'='*80}")
        print(f"用户数量: {self.num_users}")
        print(f"每用户消息数: {self.messages_per_user}")
        print(f"总消息数: {self.num_users * self.messages_per_user}")
        print(f"{'='*80}\n")

        await self.setup()
        self.report.start_time = datetime.now()

        # 阶段 1: 并发发送消息
        print("阶段 1: 并发发送消息...")
        send_tasks = [self.send_messages_for_user(user_id) for user_id in range(1, self.num_users + 1)]
        await asyncio.gather(*send_tasks)
        
        self.report.total_messages_sent = self.num_users * self.messages_per_user
        print(f"✓ 已发送 {self.report.total_messages_sent} 条消息")

        # 阶段 2: 并发消费消息
        print("\n阶段 2: 并发消费消息...")
        consume_tasks = [self.consume_messages_for_user(user_id) for user_id in range(1, self.num_users + 1)]
        await asyncio.gather(*consume_tasks)
        
        self.report.total_messages_consumed = sum(len(ids) for ids in self.consumed_ids.values())
        print(f"✓ 已消费 {self.report.total_messages_consumed} 条消息")

        # 阶段 3: 检查 Redis 内存
        print("\n阶段 3: 检查 Redis 内存...")
        await self.check_redis_memory()
        print(f"✓ Redis 内存使用: {self.report.redis_memory_used_mb:.2f} MB / {self.report.redis_memory_limit_mb:.2f} MB")

        self.report.end_time = datetime.now()

        # 计算性能指标
        duration = (self.report.end_time - self.report.start_time).total_seconds()
        self.report.throughput = self.report.total_messages_sent / duration if duration > 0 else 0
        
        if self.latencies:
            self.report.avg_latency_ms = sum(self.latencies) / len(self.latencies)
            self.report.max_latency_ms = max(self.latencies)
            self.report.min_latency_ms = min(self.latencies)

        await self.cleanup()
        
        return self.report

    def print_report(self):
        """打印测试报告"""
        report_dict = self.report.to_dict()
        
        print(f"\n{'='*80}")
        print(f"压力测试报告")
        print(f"{'='*80}")
        
        print(f"\n【测试时间】")
        print(f"  开始时间: {report_dict['test_time']['start']}")
        print(f"  结束时间: {report_dict['test_time']['end']}")
        print(f"  持续时间: {report_dict['test_time']['duration_seconds']:.2f} 秒")
        
        print(f"\n【消息统计】")
        print(f"  发送消息: {report_dict['message_stats']['total_sent']}")
        print(f"  消费消息: {report_dict['message_stats']['total_consumed']}")
        print(f"  丢失消息: {report_dict['message_stats']['total_lost']} ({report_dict['message_stats']['loss_rate']})")
        print(f"  重复消息: {report_dict['message_stats']['total_duplicate']} ({report_dict['message_stats']['duplicate_rate']})")
        
        print(f"\n【性能指标】")
        print(f"  吞吐量: {report_dict['performance']['throughput_msgs_per_sec']} 消息/秒")
        print(f"  平均延迟: {report_dict['performance']['avg_latency_ms']:.2f} ms")
        print(f"  最大延迟: {report_dict['performance']['max_latency_ms']:.2f} ms")
        print(f"  最小延迟: {report_dict['performance']['min_latency_ms']:.2f} ms")
        
        print(f"\n【Redis 内存】")
        print(f"  已使用: {report_dict['redis']['memory_used_mb']:.2f} MB")
        print(f"  限制: {report_dict['redis']['memory_limit_mb']:.2f} MB")
        print(f"  状态: {'✓ 正常' if report_dict['redis']['memory_limit_ok'] else '✗ 超限'}")
        
        if report_dict['errors']:
            print(f"\n【错误信息】")
            for error in report_dict['errors'][:10]:  # 只显示前 10 条
                print(f"  - {error}")
        
        print(f"\n【测试结果】")
        if report_dict['success']:
            print(f"  ✓ 测试通过 - 所有消息正确投递，Redis 内存限制未突破")
        else:
            print(f"  ✗ 测试失败")
        
        print(f"\n{'='*80}\n")


async def main():
    """主函数"""
    # 运行压力测试
    test = ConcurrentStressTest(num_users=10, messages_per_user=100)
    report = await test.run()
    
    # 打印报告
    test.print_report()
    
    # 返回退出码
    return 0 if report.to_dict()['success'] else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
