"""
PushMe 推送服务

用于向用户发送手机推送通知，基于 https://push.i-i.me/ 服务
"""
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

# PushMe API 地址
PUSHME_API_URL = "https://push.i-i.me"

# 消息类型
class PushMessageType:
    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"
    DATA = "data"


# 消息主题标识
class PushTheme:
    INFO = "[i]"        # 信息
    SUCCESS = "[s]"     # 成功
    WARNING = "[w]"     # 警告
    FAILURE = "[f]"     # 失败


class PushMeService:
    """
    PushMe 推送服务
    
    使用方法：
    1. 用户在 PushMe APP 上获取 push_key
    2. 在系统中配置 push_key
    3. 调用 send 方法发送推送
    
    API 文档：https://push.i-i.me/docs/index
    """
    
    def __init__(self, timeout: float = 10.0):
        """
        初始化推送服务
        
        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def send(
        self,
        push_key: str,
        title: str,
        content: str,
        msg_type: str = PushMessageType.TEXT,
        theme: Optional[str] = None,
    ) -> bool:
        """
        发送推送消息
        
        Args:
            push_key: 用户在 PushMe APP 上获取的密钥
            title: 消息标题
            content: 消息内容
            msg_type: 消息类型
            theme: 消息主题
        
        Returns:
            bool: 是否发送成功
        """
        if not push_key:
            logger.warning("push_key 为空，跳过推送")
            return False
        
        # 添加主题标识到标题
        final_title = title
        if theme:
            final_title = f"{theme}{title}"
        
        payload = {
            "push_key": push_key,
            "title": final_title,
            "content": content,
            "type": msg_type,
        }
        
        try:
            client = await self._get_client()
            response = await client.post(
                PUSHME_API_URL,
                json=payload,
            )
            
            result = response.text
            
            if result == "success":
                logger.info(f"PushMe 推送成功: title={final_title}")
                return True
            else:
                logger.warning(f"PushMe 推送失败: {result}")
                return False
                
        except httpx.TimeoutException:
            logger.error("PushMe 推送超时")
            return False
        except Exception as e:
            logger.error(f"PushMe 推送异常: {e}")
            return False
    
    async def send_task_notification(
        self,
        push_key: str,
        task_content: str,
        response: str,
        success: bool = True,
    ) -> bool:
        """
        发送定时任务执行通知
        
        Args:
            push_key: 用户推送密钥
            task_content: 任务内容
            response: 执行结果
            success: 是否执行成功
        
        Returns:
            bool: 是否推送成功
        """
        if success:
            title = "定时任务执行成功"
            theme = PushTheme.SUCCESS
        else:
            title = "定时任务执行失败"
            theme = PushTheme.FAILURE
        
        content = f"**任务内容:** {task_content}\n\n**执行结果:**\n{response}"
        
        return await self.send(
            push_key=push_key,
            title=title,
            content=content,
            msg_type=PushMessageType.MARKDOWN,
            theme=theme,
        )
    
    async def send_reminder(
        self,
        push_key: str,
        reminder_content: str,
    ) -> bool:
        """
        发送提醒通知
        
        Args:
            push_key: 用户推送密钥
            reminder_content: 提醒内容
        
        Returns:
            bool: 是否推送成功
        """
        return await self.send(
            push_key=push_key,
            title="提醒",
            content=reminder_content,
            msg_type=PushMessageType.TEXT,
            theme=PushTheme.INFO,
        )


# 全局推送服务实例
_pushme_service: Optional[PushMeService] = None


def get_pushme_service() -> PushMeService:
    """获取全局推送服务实例"""
    global _pushme_service
    if _pushme_service is None:
        _pushme_service = PushMeService()
    return _pushme_service


async def close_pushme_service():
    """关闭全局推送服务"""
    global _pushme_service
    if _pushme_service:
        await _pushme_service.close()
        _pushme_service = None
