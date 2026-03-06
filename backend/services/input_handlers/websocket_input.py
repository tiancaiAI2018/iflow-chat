"""
WebSocket 输入处理器

处理来自 WebSocket 的用户输入，通过 EventBus 发射 user_message 信号。
"""
from typing import Optional, Any
from backend.services.event_bus import EventBus


class WebSocketInputHandler:
    """
    WebSocket 输入处理器

    负责将 WebSocket 接收的用户消息转换为 EventBus 信号，
    实现输入层与业务逻辑层的解耦。

    使用示例：
        handler = WebSocketInputHandler()
        handler.handle(user_id=1, content="Hello", conversation_id=100)

        # 带自定义 sender
        handler = WebSocketInputHandler(sender='websocket_client')
        handler.handle(user_id=1, content="Hello")
    """

    def __init__(self, sender: Optional[str] = None):
        """
        初始化 WebSocket 输入处理器

        Args:
            sender: 发送者标识（可选），用于追踪消息来源
        """
        self.sender = sender

    def handle(
        self,
        user_id: int,
        content: str,
        conversation_id: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        处理用户输入，发射 user_message 信号

        Args:
            user_id: 用户 ID
            content: 消息内容
            conversation_id: 会话 ID（可选）
            **kwargs: 额外参数（如 metadata 等）

        Example:
            handler.handle(
                user_id=123,
                content="你好",
                conversation_id=456,
                metadata={'source': 'mobile'}
            )
        """
        # 构建信号参数
        signal_kwargs = {
            'user_id': user_id,
            'content': content,
        }

        # 添加可选参数
        if conversation_id is not None:
            signal_kwargs['conversation_id'] = conversation_id

        # 添加额外参数
        signal_kwargs.update(kwargs)

        # 发射信号
        EventBus.emit('user_message', sender=self.sender, **signal_kwargs)
