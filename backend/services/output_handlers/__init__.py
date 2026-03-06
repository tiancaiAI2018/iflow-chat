"""
输出处理器模块

提供不同输出目标的适配器，订阅 EventBus 信号并将消息推送到对应目标。

可用的输出处理器：
- RedisOutputHandler: 推送消息到 Redis Stream（用于 WebSocket 断线恢复）
- DBOutputHandler: 存储完整响应到数据库（未来实现）
"""
from services.output_handlers.redis_output import RedisOutputHandler

__all__ = ['RedisOutputHandler']
