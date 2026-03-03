"""
错误处理服务
提供 WebSocket 重连、iFlow 服务不可用处理、任务失败重试等功能
"""
import asyncio
import logging
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举"""
    WEBSOCKET_DISCONNECT = "websocket_disconnect"
    IFLOW_UNAVAILABLE = "iflow_unavailable"
    TASK_EXECUTION_FAILED = "task_execution_failed"
    TOKEN_EXPIRED = "token_expired"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    """错误信息"""
    type: ErrorType
    message: str
    original_error: Optional[Exception] = None
    retry_count: int = 0
    max_retries: int = 3
    retry_after: Optional[float] = None  # 重试等待时间（秒）
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ReconnectManager:
    """
    WebSocket 重连管理器
    处理网络断开后的自动重连逻辑
    """
    
    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
    ):
        """
        初始化重连管理器
        
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
            exponential_base: 指数退避基数
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def calculate_delay(self, retry_count: int) -> float:
        """
        计算重试延迟时间（指数退避）
        
        Args:
            retry_count: 当前重试次数
        
        Returns:
            float: 延迟时间（秒）
        """
        delay = self.base_delay * (self.exponential_base ** retry_count)
        return min(delay, self.max_delay)
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        on_retry: Optional[Callable[[int, float], None]] = None,
        **kwargs,
    ) -> Any:
        """
        带重试的执行函数
        
        Args:
            func: 要执行的异步函数
            on_retry: 重试回调函数
            *args, **kwargs: 传递给func 的参数
        
        Returns:
            函数执行结果
        
        Raises:
            Exception: 超过最大重试次数后抛出最后一次异常
        """
        last_error = None
        
        for retry_count in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                if retry_count < self.max_retries:
                    delay = self.calculate_delay(retry_count)
                    logger.warning(
                        f"Operation failed (attempt {retry_count + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    if on_retry:
                        on_retry(retry_count, delay)
                    
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Operation failed after {self.max_retries + 1} attempts: {e}")
        
        raise last_error


class IFlowServiceMonitor:
    """
    iFlow 服务监控器
    检测服务可用性，处理服务不可用场景
    """
    
    def __init__(
        self,
        health_check_interval: float = 60.0,
        unhealthy_threshold: int = 3,
        recovery_threshold: int = 2,
    ):
        """
        初始化服务监控器
        
        Args:
            health_check_interval: 健康检查间隔（秒）
            unhealthy_threshold: 判定为不健康的连续失败次数
            recovery_threshold: 判定为恢复的连续成功次数
        """
        self.health_check_interval = health_check_interval
        self.unhealthy_threshold = unhealthy_threshold
        self.recovery_threshold = recovery_threshold
        
        self._is_healthy = True
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_check_time: Optional[datetime] = None
        self._last_error: Optional[str] = None
    
    @property
    def is_healthy(self) -> bool:
        """服务是否健康"""
        return self._is_healthy
    
    @property
    def last_error(self) -> Optional[str]:
        """最后一次错误信息"""
        return self._last_error
    
    def record_success(self):
        """记录成功"""
        self._consecutive_failures = 0
        self._consecutive_successes += 1
        self._last_check_time = datetime.now()
        
        if self._consecutive_successes >= self.recovery_threshold:
            if not self._is_healthy:
                logger.info("iFlow service recovered")
            self._is_healthy = True
    
    def record_failure(self, error: str):
        """
        记录失败
        
        Args:
            error: 错误信息
        """
        self._consecutive_successes = 0
        self._consecutive_failures += 1
        self._last_check_time = datetime.now()
        self._last_error = error
        
        if self._consecutive_failures >= self.unhealthy_threshold:
            if self._is_healthy:
                logger.error(f"iFlow service marked as unhealthy: {error}")
            self._is_healthy = False
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取服务状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            "is_healthy": self._is_healthy,
            "consecutive_failures": self._consecutive_failures,
            "consecutive_successes": self._consecutive_successes,
            "last_check_time": self._last_check_time.isoformat() if self._last_check_time else None,
            "last_error": self._last_error,
        }


class TaskRetryHandler:
    """
    任务执行重试处理器
    处理任务执行失败后的重试逻辑
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ):
        """
        初始化重试处理器
        
        Args:
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        on_failure: Optional[Callable[[int, Exception], None]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        带重试的任务执行
        
        Args:
            func: 要执行的异步函数
            on_failure: 失败回调函数
            *args, **kwargs: 传递给 func 的参数
        
        Returns:
            Dict: 执行结果
        """
        last_error = None
        
        for retry_count in range(self.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                result["retries"] = retry_count
                return result
            except Exception as e:
                last_error = e
                
                if retry_count < self.max_retries:
                    logger.warning(
                        f"Task execution failed (attempt {retry_count + 1}): {e}. "
                        f"Retrying in {self.retry_delay}s..."
                    )
                    
                    if on_failure:
                        on_failure(retry_count, e)
                    
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"Task execution failed after {self.max_retries + 1} attempts: {e}")
        
        return {
            "success": False,
            "error": str(last_error),
            "retries": self.max_retries,
        }


class TokenRefreshHandler:
    """
    Token 刷新处理器
    处理 Token 过期后的自动刷新逻辑
    """
    
    def __init__(
        self,
        refresh_threshold_minutes: int = 5,
    ):
        """
        初始化 Token 刷新处理器
        
        Args:
            refresh_threshold_minutes: Token 过期前多少分钟开始刷新
        """
        self.refresh_threshold_minutes = refresh_threshold_minutes
    
    def should_refresh(self, token_payload: Dict[str, Any]) -> bool:
        """
        判断是否需要刷新 Token
        
        Args:
            token_payload: Token 解码后的 payload
        
        Returns:
            bool: 是否需要刷新
        """
        if "exp" not in token_payload:
            return True
        
        from datetime import timedelta
        exp_time = datetime.fromtimestamp(token_payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # 如果 Token 将在阈值时间内过期，则需要刷新
        return (exp_time - now) < timedelta(minutes=self.refresh_threshold_minutes)
    
    def is_expired(self, token_payload: Dict[str, Any]) -> bool:
        """
        判断 Token 是否已过期
        
        Args:
            token_payload: Token 解码后的 payload
        
        Returns:
            bool: 是否已过期
        """
        if "exp" not in token_payload:
            return True
        
        exp_time = datetime.fromtimestamp(token_payload["exp"], tz=timezone.utc)
        return datetime.now(timezone.utc) > exp_time


# 导入 timezone
from datetime import timezone


# 全局实例
_reconnect_manager: Optional[ReconnectManager] = None
_iflow_monitor: Optional[IFlowServiceMonitor] = None
_task_retry_handler: Optional[TaskRetryHandler] = None
_token_refresh_handler: Optional[TokenRefreshHandler] = None


def get_reconnect_manager() -> ReconnectManager:
    """获取重连管理器单例"""
    global _reconnect_manager
    if _reconnect_manager is None:
        _reconnect_manager = ReconnectManager()
    return _reconnect_manager


def get_iflow_monitor() -> IFlowServiceMonitor:
    """获取 iFlow 服务监控器单例"""
    global _iflow_monitor
    if _iflow_monitor is None:
        _iflow_monitor = IFlowServiceMonitor()
    return _iflow_monitor


def get_task_retry_handler() -> TaskRetryHandler:
    """获取任务重试处理器单例"""
    global _task_retry_handler
    if _task_retry_handler is None:
        _task_retry_handler = TaskRetryHandler()
    return _task_retry_handler


def get_token_refresh_handler() -> TokenRefreshHandler:
    """获取 Token 刷新处理器单例"""
    global _token_refresh_handler
    if _token_refresh_handler is None:
        _token_refresh_handler = TokenRefreshHandler()
    return _token_refresh_handler
