"""
iFlow 连接池管理器

管理用户连接的生命周期，支持：
1. 同用户同会话：复用现有连接
2. 同用户同会话但连接断开：创建新连接
3. 同用户切换会话：创建新连接，旧连接在 TaskFinishMessage 后自动关闭

端口栈机制：
- IFlowClientService 维护端口栈 _user_ports[user_id] = [port_new, port_old, ...]
- 新连接创建时，端口自动压栈
- 旧连接在收到 TaskFinishMessage 时，检查是否在栈顶，不在则自动关闭
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from backend.services.iflow_client import IFlowClientService
from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ConnectionEntry:
    """连接条目"""
    client: IFlowClientService
    user_id: int
    conversation_id: int
    port: int
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: datetime = field(default_factory=datetime.now)


class IFlowConnectionPool:
    """
    iFlow 连接池管理器
    
    管理策略：
    1. 每个用户维护一个活跃连接（端口栈顶）
    2. 同用户同会话：复用连接
    3. 同用户切换会话：创建新连接，旧连接等 TaskFinishMessage 后自动关闭
    4. 空闲超时：30分钟未使用自动关闭
    
    端口栈机制：
    - IFlowClientService._user_ports[user_id] = [port_new, port_old, ...]
    - 新连接创建时，端口自动压栈（由 IFlowClientService.connect() 处理）
    - 旧连接在 TaskFinishMessage 时自动关闭（由 IFlowClientService.query_stream() 处理）
    """
    
    def __init__(
        self,
        idle_timeout_minutes: int = 30,
    ):
        """
        初始化连接池
        
        Args:
            idle_timeout_minutes: 空闲超时时间（分钟），默认 30 分钟
        """
        self.idle_timeout = timedelta(minutes=idle_timeout_minutes)
        
        # user_id -> ConnectionEntry（只维护当前活跃连接）
        self._connections: Dict[int, ConnectionEntry] = {}
        
        # 保护连接池操作的锁
        self._lock = asyncio.Lock()
        
        # 后台清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"IFlowConnectionPool initialized: idle_timeout={idle_timeout_minutes}min")
    
    async def start(self):
        """启动连接池（开始后台清理任务）"""
        if self._running:
            return
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("IFlowConnectionPool started")
    
    async def stop(self):
        """停止连接池（关闭所有连接）"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        async with self._lock:
            for user_id, entry in list(self._connections.items()):
                try:
                    await entry.client.disconnect()
                    logger.info(f"Closed connection for user {user_id}, port={entry.port}")
                except Exception as e:
                    logger.warning(f"Error closing connection for user {user_id}: {e}")
            self._connections.clear()
        
        logger.info("IFlowConnectionPool stopped")
    
    async def get_connection(
        self,
        user_id: int,
        conversation_id: int,
        working_directory: str,
        iflow_session_id: Optional[str] = None,
    ) -> IFlowClientService:
        """
        获取或创建连接
        
        策略：
        1. 用户无连接 → 创建新连接
        2. 用户有连接且会话相同且连接可用 → 复用连接
        3. 用户有连接且会话相同但连接断开 → 创建新连接，旧连接会被端口栈清理
        4. 用户有连接但会话不同 → 创建新连接（端口自动压栈），旧连接等 TaskFinishMessage 后自动关闭
        
        Args:
            user_id: 用户 ID
            conversation_id: 会话 ID
            working_directory: 工作目录
            iflow_session_id: iFlow 会话 ID（可选，用于恢复上下文）
            
        Returns:
            IFlowClientService: 连接实例
        """
        async with self._lock:
            entry = self._connections.get(user_id)
            
            # 情况 1: 用户无连接
            if entry is None:
                return await self._create_connection(user_id, conversation_id, working_directory, iflow_session_id)
            
            # 情况 2: 同用户同会话且连接可用 → 复用
            if entry.conversation_id == conversation_id and entry.client.is_connected:
                entry.last_used_at = datetime.now()
                logger.debug(f"Reusing connection for user {user_id}, conversation {conversation_id}, port={entry.port}")
                return entry.client
            
            # 情况 3 & 4: 会话不同或连接断开 → 创建新连接
            # 旧连接会被端口栈机制自动清理（在 TaskFinishMessage 时）
            if entry.conversation_id != conversation_id:
                logger.info(
                    f"User {user_id} switching conversation: "
                    f"{entry.conversation_id} -> {conversation_id}, old port={entry.port}"
                )
            else:
                logger.info(f"Connection for user {user_id} disconnected, creating new connection")
            
            # 创建新连接（IFlowClientService.connect() 会自动将新端口压栈）
            return await self._create_connection(user_id, conversation_id, working_directory, iflow_session_id)
    
    async def _create_connection(
        self,
        user_id: int,
        conversation_id: int,
        working_directory: str,
        iflow_session_id: Optional[str] = None,
    ) -> IFlowClientService:
        """
        创建新连接
        
        创建新连接前会检查并清理空闲的旧连接：
        - 如果旧连接正在输出（_is_streaming=True），等待 TaskFinish 后自动关闭
        - 如果旧连接空闲（_is_streaming=False），立即关闭
        
        IFlowClientService.connect() 会自动：
        1. 分配新端口
        2. 将新端口压入端口栈顶
        
        Args:
            user_id: 用户 ID
            conversation_id: 会话 ID
            working_directory: 工作目录
            iflow_session_id: iFlow 会话 ID（可选，用于恢复上下文）
            
        Returns:
            IFlowClientService: 新创建的连接实例
        """
        # 检查是否存在旧连接
        old_entry = self._connections.get(user_id)
        if old_entry:
            # 如果旧连接空闲或已断开，直接关闭
            if not old_entry.client._is_streaming or not old_entry.client.is_connected:
                old_port = old_entry.port
                logger.info(
                    f"Closing idle/disconnected old connection: user={user_id}, "
                    f"port={old_port}, is_streaming={old_entry.client._is_streaming}, "
                    f"is_connected={old_entry.client.is_connected}"
                )
                try:
                    await old_entry.client.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing old connection port {old_port}: {e}")
            else:
                # 旧连接正在输出，不关闭，等待 TaskFinish 自动清理
                logger.info(
                    f"Old connection still streaming, will be cleaned by TaskFinish: "
                    f"user={user_id}, port={old_entry.port}"
                )
        
        client = IFlowClientService(
            cwd=working_directory,
            user_id=user_id,
            session_id=iflow_session_id,  # 传入 session_id 以恢复上下文
        )
        
        await client.connect()
        
        # 记录连接
        entry = ConnectionEntry(
            client=client,
            user_id=user_id,
            conversation_id=conversation_id,
            port=client._port,
        )
        self._connections[user_id] = entry
        
        # 获取用户的端口栈信息
        user_ports = IFlowClientService._get_user_ports(user_id)
        logger.info(
            f"Created new connection: user={user_id}, "
            f"conversation={conversation_id}, port={client._port}, "
            f"session_id={client.session_id}, port_stack={user_ports}"
        )
        
        return client
    
    async def _remove_connection(self, user_id: int):
        """移除并关闭连接"""
        entry = self._connections.pop(user_id, None)
        if entry:
            try:
                await entry.client.disconnect()
                logger.info(f"Removed connection for user {user_id}, port={entry.port}")
            except Exception as e:
                logger.warning(f"Error removing connection for user {user_id}: {e}")
    
    async def release_connection(self, user_id: int, keep_alive: bool = True):
        """
        释放连接
        
        Args:
            user_id: 用户 ID
            keep_alive: 是否保持连接（用于空闲超时清理）
        """
        async with self._lock:
            entry = self._connections.get(user_id)
            if entry:
                if keep_alive:
                    # 更新最后使用时间
                    entry.last_used_at = datetime.now()
                else:
                    # 立即关闭
                    await self._remove_connection(user_id)
    
    async def interrupt_connection(self, user_id: int) -> bool:
        """
        中断用户当前正在执行的任务
        
        获取用户的活跃连接并调用 interrupt 方法取消当前任务。
        中断后连接会被关闭，下次使用时需要重新连接。
        
        Args:
            user_id: 用户 ID
            
        Returns:
            bool: 是否中断成功
        """
        async with self._lock:
            entry = self._connections.get(user_id)
            
            if entry is None:
                logger.warning(f"No active connection for user {user_id} to interrupt")
                return False
            
            if not entry.client.is_connected:
                logger.warning(f"Connection for user {user_id} is not connected")
                return False
            
            try:
                logger.info(f"Interrupting connection for user {user_id}, port={entry.port}")
                result = await entry.client.interrupt()
                
                if result:
                    # 中断成功后，从池中移除连接（连接已断开）
                    self._connections.pop(user_id, None)
                    logger.info(f"Connection interrupted and removed for user {user_id}")
                
                return result
                
            except Exception as e:
                logger.error(f"Error interrupting connection for user {user_id}: {e}")
                # 出错时也移除连接
                self._connections.pop(user_id, None)
                return False
    
    def get_connection_entry(self, user_id: int) -> Optional[ConnectionEntry]:
        """
        获取用户的连接条目（不持有锁，用于快速检查）
        
        Args:
            user_id: 用户 ID
            
        Returns:
            Optional[ConnectionEntry]: 连接条目，如果不存在则返回 None
        """
        return self._connections.get(user_id)
    
    async def cleanup_idle_connections(self):
        """
        清理空闲超时的连接
        
        检查所有连接，关闭超过 idle_timeout 未使用的连接
        """
        now = datetime.now()
        to_remove = []
        
        async with self._lock:
            for user_id, entry in list(self._connections.items()):
                idle_time = now - entry.last_used_at
                if idle_time > self.idle_timeout:
                    to_remove.append((user_id, entry, idle_time))
        
        # 关闭空闲连接
        for user_id, entry, idle_time in to_remove:
            logger.info(
                f"Closing idle connection: user={user_id}, "
                f"idle_time={idle_time.total_seconds():.0f}s, port={entry.port}"
            )
            async with self._lock:
                if self._connections.get(user_id) is entry:
                    await self._remove_connection(user_id)
    
    async def _cleanup_loop(self):
        """后台清理循环"""
        while self._running:
            try:
                # 每 5 分钟检查一次空闲连接
                await asyncio.sleep(300)
                await self.cleanup_idle_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        now = datetime.now()
        stats = {
            "total_connections": len(self._connections),
            "connections": []
        }
        
        for user_id, entry in self._connections.items():
            stats["connections"].append({
                "user_id": user_id,
                "conversation_id": entry.conversation_id,
                "port": entry.port,
                "age_seconds": (now - entry.created_at).total_seconds(),
                "idle_seconds": (now - entry.last_used_at).total_seconds(),
                "is_connected": entry.client.is_connected,
                "port_stack": IFlowClientService._get_user_ports(user_id),
            })
        
        return stats


# 全局连接池实例
_connection_pool: Optional[IFlowConnectionPool] = None


def get_connection_pool() -> IFlowConnectionPool:
    """
    获取全局连接池实例
    
    Returns:
        IFlowConnectionPool: 连接池实例
    """
    global _connection_pool
    if _connection_pool is None:
        # 从配置读取超时时间
        idle_timeout = getattr(settings, 'IFLOW_IDLE_TIMEOUT_MINUTES', 30)
        _connection_pool = IFlowConnectionPool(
            idle_timeout_minutes=idle_timeout,
        )
    return _connection_pool


async def start_connection_pool():
    """启动全局连接池"""
    pool = get_connection_pool()
    await pool.start()


async def stop_connection_pool():
    """停止全局连接池"""
    global _connection_pool
    if _connection_pool:
        await _connection_pool.stop()
        _connection_pool = None