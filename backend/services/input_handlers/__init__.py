"""
输入处理器模块

提供不同输入源的适配器，统一通过 EventBus 发射 user_message 信号。

可用的输入处理器：
- WebSocketInputHandler: WebSocket 连接输入
"""
from .websocket_input import WebSocketInputHandler

__all__ = ['WebSocketInputHandler']
