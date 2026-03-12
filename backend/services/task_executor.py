"""
任务执行服务
定时任务触发后执行：调用 iFlow、保存通知、WebSocket 推送、PushMe 手机推送
包含错误处理和重试机制
支持详细日志记录和通知推送优化
支持 PushMe 手机推送通知
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from backend.services.iflow_client import IFlowClientService, MessageType
from backend.services.websocket_manager import get_websocket_manager, WebSocketManager
from backend.services.notification_store import NotificationStore, get_notification_store
from backend.services.pushme_service import get_pushme_service
from backend.database import async_session_maker
from backend.models.user import User
from sqlalchemy import select

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
        logger.info(f"========================================")
        logger.info(f"[TaskExecutor] Starting task execution")
        logger.info(f"  user_id: {user_id}")
        logger.info(f"  task_id: {task_id}")
        logger.info(f"  content: {content[:100]}...")
        logger.info(f"  timestamp: {datetime.now().isoformat()}")
        logger.info(f"========================================")
        
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
                logger.info(f"[TaskExecutor] Attempt {retry_count + 1}/{self.max_retries + 1}")
                
                # 1. 调用 iFlow 执行任务
                logger.info(f"[TaskExecutor] Calling iFlow...")
                response = await self._call_iflow(content, task_id)
                result["response"] = response
                result["success"] = True
                result["retries"] = retry_count
                logger.info(f"[TaskExecutor] iFlow response received: {response[:100]}...")
                
                # 2. 构建通知内容
                notification_content = self._build_notification_content(task_id, content, response)
                logger.info(f"[TaskExecutor] Notification content prepared")
                
                # 3. 保存通知到文件（必须执行）
                logger.info(f"[TaskExecutor] Saving notification to store...")
                notification = self.notification_store.add_notification(
                    user_id=user_id,
                    task_id=task_id,
                    content=notification_content,
                )
                result["notification"] = notification
                logger.info(f"[TaskExecutor] Notification saved: id={notification.get('id')}")
                
                # 4. 检测用户在线状态，在线则 WebSocket 推送
                is_online = self.websocket_manager.is_user_online(user_id)
                logger.info(f"[TaskExecutor] User online status: {is_online}")
                
                if is_online:
                    logger.info(f"[TaskExecutor] Attempting WebSocket push...")
                    pushed = await self._push_notification(user_id, notification)
                    result["pushed"] = pushed
                    logger.info(f"[TaskExecutor] WebSocket push result: {pushed}")
                else:
                    logger.info(f"[TaskExecutor] User offline, notification saved to store only")
                
                # 5. PushMe 手机推送（用户配置了 push_key 时）
                pushme_result = await self._pushme_notify(user_id, content, response, success=True)
                result["pushme_pushed"] = pushme_result
                
                logger.info(f"[TaskExecutor] Task execution completed successfully")
                logger.info(f"  success: {result['success']}")
                logger.info(f"  pushed: {result['pushed']}")
                logger.info(f"  retries: {result['retries']}")
                
                # 记录执行历史
                self._record_execution(task_id, result)
                
                return result
                
            except Exception as e:
                last_error = e
                result["retries"] = retry_count
                
                logger.error(f"[TaskExecutor] Attempt {retry_count + 1} failed: {e}")
                
                if retry_count < self.max_retries:
                    logger.warning(f"[TaskExecutor] Retrying in {self.retry_delay}s...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"[TaskExecutor] All {self.max_retries + 1} attempts failed")
        
        # 所有重试都失败
        result["error"] = str(last_error)
        logger.error(f"[TaskExecutor] Task execution failed: {last_error}")
        
        # 即使执行失败，也保存失败通知
        try:
            notification_content = f"【定时任务执行失败】\n任务内容: {content}\n错误: {str(last_error)}\n重试次数: {self.max_retries}"
            notification = self.notification_store.add_notification(
                user_id=user_id,
                task_id=task_id,
                content=notification_content,
            )
            result["notification"] = notification
            logger.info(f"[TaskExecutor] Failure notification saved")
        except Exception as save_error:
            logger.error(f"[TaskExecutor] Failed to save failure notification: {save_error}")
        
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
    
    async def _call_iflow(self, task_content: str, task_id: str) -> str:
        """
        调用 iFlow 执行任务
        
        使用 task_id 生成独立的 user_id，避免和用户聊天连接冲突。
        定时任务的连接是一次性的，执行完毕自动关闭。
        
        Args:
            task_content: 任务内容
            task_id: 任务 ID，用于生成独立的 user_id
        
        Returns:
            str: iFlow 响应
        """
        # 用 task_id 哈希生成独立的负数 user_id，不和用户聊天冲突
        # 范围: -1 到 -10000，确保不和正数 user_id 冲突
        task_user_id = -abs(hash(task_id) % 10000) - 1
        logger.debug(f"Task {task_id} using isolated user_id={task_user_id}")
        
        # 构建带上下文的提示，让 iFlow 知道这是定时任务执行
        context_message = f"""【定时任务触发通知】

这是你之前帮用户创建的定时任务，现在时间到了，任务被触发执行。

任务内容：{task_content}

请直接执行这个任务，不要再次询问用户创建任务的细节。如果这是一个提醒任务，请直接给出提醒内容。"""
        
        full_response = []
        
        # 使用独立的 user_id 创建连接，避免和用户聊天冲突
        async with IFlowClientService(user_id=task_user_id) as client:
            async for msg in client.query_stream(context_message):
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
        # 直接展示 iFlow 的响应结果
        # iFlow 会根据上下文提示，返回合适的执行结果
        return f"【定时任务】\n任务: {task_content}\n\n{response}"
    
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
    
    async def _pushme_notify(
        self,
        user_id: int,
        task_content: str,
        response: str,
        success: bool = True,
    ) -> bool:
        """
        通过 PushMe 发送手机推送通知
        
        Args:
            user_id: 用户 ID
            task_content: 任务内容
            response: 执行结果
            success: 是否执行成功
        
        Returns:
            bool: 是否推送成功
        """
        try:
            # 从数据库获取用户的 push_key
            async with async_session_maker() as db:
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user or not user.push_key:
                    logger.debug(f"User {user_id} has no push_key configured, skipping PushMe")
                    return False
                
                # 发送 PushMe 推送
                pushme = get_pushme_service()
                pushed = await pushme.send_task_notification(
                    push_key=user.push_key,
                    task_content=task_content,
                    response=response,
                    success=success,
                )
                
                if pushed:
                    logger.info(f"[TaskExecutor] PushMe notification sent to user {user_id}")
                else:
                    logger.warning(f"[TaskExecutor] PushMe notification failed for user {user_id}")
                
                return pushed
                
        except Exception as e:
            logger.error(f"[TaskExecutor] Error sending PushMe notification: {e}")
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
