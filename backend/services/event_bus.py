"""
EventBus 信号系统

基于 blinker 实现的事件总线，用于解耦输入输出组件。

信号定义：
- user_message: 用户输入消息
- ai_response: AI 流式响应（增量）
- ai_complete: AI 响应完成（完整）

使用示例：
    # 订阅信号
    @EventBus.on('user_message')
    def handle_user_message(sender, **kwargs):
        print(f"收到用户消息: {kwargs}")

    # 发射信号
    EventBus.emit('user_message', user_id=1, content="Hello")
"""
from blinker import Signal


class EventBus:
    """
    事件总线类

    使用 blinker.Signal 实现发布-订阅模式，
    支持多个订阅者监听同一信号。
    """

    # 用户输入消息信号
    # 参数：user_id (int), content (str), conversation_id (int, optional)
    user_message = Signal('user_message')

    # AI 流式响应信号（增量）
    # 参数：user_id (int), content (str), is_delta (bool), metadata (dict, optional)
    ai_response = Signal('ai_response')

    # AI 响应完成信号（完整响应）
    # 参数：user_id (int), content (str), conversation_id (int, optional), metadata (dict, optional)
    ai_complete = Signal('ai_complete')

    # 工具调用信号
    # 参数：user_id (int), tool_name (str), tool_args (dict), result (any, optional), metadata (dict, optional)
    tool_call = Signal('tool_call')
    # 任务计划信号
    # 参数：user_id (int), entries (list), conversation_id (int, optional), request_id (str, optional)
    plan = Signal('plan')

    @classmethod
    def emit(cls, signal_name: str, sender=None, **kwargs):
        """
        发射信号

        Args:
            signal_name: 信号名称（user_message, ai_response, ai_complete）
            sender: 发送者标识（可选）
            **kwargs: 信号参数

        Raises:
            AttributeError: 信号名称不存在

        Example:
            EventBus.emit('user_message', user_id=1, content="Hello")
            EventBus.emit('ai_response', sender='iflow_client', user_id=1, content="Hi")
        """
        signal = getattr(cls, signal_name, None)
        if signal is None:
            raise AttributeError(f"EventBus 没有名为 '{signal_name}' 的信号")
        signal.send(sender, **kwargs)

    @classmethod
    def on(cls, signal_name: str):
        """
        订阅信号装饰器

        Args:
            signal_name: 信号名称（user_message, ai_response, ai_complete）

        Returns:
            装饰器函数

        Raises:
            AttributeError: 信号名称不存在

        Example:
            @EventBus.on('user_message')
            def handle_user_message(sender, **kwargs):
                print(f"收到消息: {kwargs['content']}")

            # 异步处理器
            @EventBus.on('ai_response')
            async def handle_ai_response(sender, **kwargs):
                await save_to_redis(kwargs)
        """
        signal = getattr(cls, signal_name, None)
        if signal is None:
            raise AttributeError(f"EventBus 没有名为 '{signal_name}' 的信号")
        return signal.connect

    @classmethod
    def off(cls, signal_name: str, handler):
        """
        取消订阅信号

        Args:
            signal_name: 信号名称
            handler: 要取消的处理器函数

        Example:
            @EventBus.on('user_message')
            def my_handler(sender, **kwargs):
                pass

            # 取消订阅
            EventBus.off('user_message', my_handler)
        """
        signal = getattr(cls, signal_name, None)
        if signal is not None:
            signal.disconnect(handler)
