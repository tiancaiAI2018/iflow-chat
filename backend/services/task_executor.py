"""
任务执行服务
定时任务触发后执行：调用 iFlow、保存通知、WebSocket 推送
包含错误处理和重试机制
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from backend.services.iflow_client import IFlowClientService, MessageType
from backend.services.websocket_manager import get_websocket_manager, WebSocketManager
from backend.services.notification_store import NotificationStore, get_notification_store

logger = logging.getLogger(__name__)


class TaskExecutor:
    """
    任务执行器
    执行定时任务：调用 iFlow、保存通知、WebSocket 推送
    包含错误处理和重试机制
    """
    
    def __init__(
        self,
        notification_store: Optional[NotificationStore] = None,
        websocket_manager: Optional[WebSocketManager] = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ):
        self.notification_store = notification_store or NotificationStore()
        self.websocket_manager = websocket_manager or get_websocket_manager()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._execution_history: Dict[str, list] = {}  # 任务执行历史
    
    async def execute_task(
        self,
        user_id: int,
        task_id: str,
        content: str,
    ) -> Dict[str, Any]:
        """
        执行任务（带重试机制）
        
        Args:
            user_id: 用户 ID
            task_id: 任务 ID
            content: 任务内容（发送给 iFlow 的消息）
        
        Returns:
            Dict: 执行结果
        """
        logger.info(f"Executing task: user_id={user_id}, task_id={task_id}, content={content[:50]}...")
        
        result = {
            "success": False,
            "task_id": task_id,
            "user_id": user_id,
            "content": content,
            "response": None,
            "error": None,
            "notification": None,
            "pushed": False,
            "retries": 0,
            "executed_at": datetime.now().isoformat(),
        }
        
        last_error = None
        
        # 带重试的执行
        for retry_count in range(self.max_retries + 1):
            try:
                # 1. 调用 iFlow 执行任务
                response = await self._call_iflow(content)
                result["response"] = response
                result["success"] = True
                result["retries"] = retry_count
                
                # 2. 构建通知内容
                notification_content = self._build_notification_content(task_id, content, response)
                
                # 3. 保存通知到文件（必须执行）
                notification = self.notification_store.add_notification(
                    user_id=user_id,
                    task_id=task_id,
                    content=notification_content,
                )
                result["notification"] = notification
                
                # 4. 检测用户在线状态，在线则 WebSocket 推送
                if self.websocket_manager.is_user_online(user_id):
                    pushed = await self._push_notification(user_id, notification)
                    result["pushed"] = pushed
                
                logger.info(f"Task executed successfully: task_id={task_id}, pushed={result['pushed']}, retries={retry_count}")
                
                # 记录执行历史
                self._record_execution(task_id, result)
                
                return result
                
            except Exception as e:
                last_error = e
                result["retries"] = retry_count
                
                if retry_count < self.max_retries:
                    logger.warning(
                        f"Task execution failed (attempt {retry_count + 1}): {e}. "
                        f"Retrying in {self.retry_delay}s..."
                    )
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"Task execution failed after {self.max_retries + 1} attempts: {e}")
        
        # 所有重试都失败
        result["error"] = str(last_error)
        
        # 即使执行失败，也保存失败通知
        try:
            notification_content = f"【定时任务执行失败】\n任务内容: {content}\n错误: {str(last_error)}\n重试次数: {self.max_retries}"
            notification = self.notification_store.add_notification(
                user_id=user_id,
                task_id=task_id,
                content=notification_content,
            )
            result["notification"] = notification
        except Exception as save_error:
            logger.error(f"Failed to save failure notification: {save_error}")
        
        # 记录执行历史
        self._record_execution(task_id, result)
        
        return result
    
    def _record_execution(self, task_id: str, result: Dict[str, Any]):
        """
        记录任务执行历史
        
        Args:
            task_id: 任务 ID
            result: 执行结果
        """
        if task_id not in self._execution_history:
            self._execution_history[task_id] = []
        
        # 只保留最近 10 次执行记录
        self._execution_history[task_id].append(result)
        if len(self._execution_history[task_id]) > 10:
            self._execution_history[task_id] = self._execution_history[task_id][-10:]
    
    def get_execution_history(self, task_id: str) -> list:
        """
        获取任务执行历史
        
        Args:
            task_id: 任务 ID
        
        Returns:
            list: 执行历史列表
        """
        return self._execution_history.get(task_id, [])
    
    async def _call_iflow(self, message: str) -> str:
        """
        调用 iFlow 执行任务
        
        Args:
            message: 任务消息
        
        Returns:
            str: iFlow 响应
        """
        full_response = []
        
        async with IFlowClientService() as client:
            async for msg in client.query_stream(message):
                if msg.type == MessageType.TEXT and msg.content:
                    full_response.append(msg.content)
                elif msg.type == MessageType.ERROR:
                    raise Exception(f"iFlow error: {msg.content}")
        
        return "".join(full_response)
    
    def _build_notification_content(
        self,
        task_id: str,
        task_content: str,
        response: str,
    ) -> str:
        """
        构建通知内容
        
        Args:
            task_id: 任务 ID
            task_content: 任务内容
            response: iFlow 响应
        
        Returns:
            str: 格式化的通知内容
        """
        return f"【定时任务执行结果】\n任务: {task_content}\n\n结果:\n{response}"
    
    async def _push_notification(
        self,
        user_id: int,
        notification: Dict[str, Any],
    ) -> bool:
        """
        通过 WebSocket 推送通知
        
        Args:
            user_id: 用户 ID
            notification: 通知对象
        
        Returns:
            bool: 是否推送成功
        """
        message = {
            "type": "notification",
            "notification": notification,
        }
        
        try:
            count = await self.websocket_manager.send_to_user(user_id, message)
            return count > 0
        except Exception as e:
            logger.error(f"Failed to push notification: {e}")
            return False


# 全局任务执行器实例
_task_executor: Optional[TaskExecutor] = None


def get_task_executor() -> TaskExecutor:
    """获取任务执行器单例"""
    global _task_executor
    if _task_executor is None:
        _task_executor = TaskExecutor(
            notification_store=get_notification_store(),
        )
    return _task_executor


async def execute_task_callback(user_id: int, task_id: str, content: str):
    """
    任务执行回调函数（供 scheduler.py 调用）
    
    Args:
        user_id: 用户 ID
        task_id: 任务 ID
        content: 任务内容
    """
    executor = get_task_executor()
    await executor.execute_task(user_id, task_id, content)
