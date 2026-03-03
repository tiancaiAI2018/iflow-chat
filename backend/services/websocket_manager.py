"""
WebSocket 连接管理服务
管理用户 WebSocket 连接、消息路由、多标签页支持
"""
import asyncio
import logging
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from fastapi import WebSocket
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """连接状态"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"


@dataclass
class ConnectionInfo:
    """连接信息"""
    websocket: WebSocket
    user_id: int
    connection_id: str  # 唯一标识每个连接（支持多标签页）
    status: ConnectionStatus = ConnectionStatus.CONNECTED
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = datetime.now()


class WebSocketManager:
    """
    WebSocket 连接管理器
    
    功能：
    - 管理用户连接（支持多标签页）
    - 消息路由和广播
    - 连接状态管理
    """
    
    def __init__(self):
        # user_id -> Dict[connection_id, ConnectionInfo] 一个用户可以有多个连接（多标签页）
        self._connections: Dict[int, Dict[str, ConnectionInfo]] = {}
        # connection_id -> ConnectionInfo 快速查找
        self._connection_map: Dict[str, ConnectionInfo] = {}
        # 连接计数器
        self._connection_counter = 0
        # 锁，保证线程安全
        self._lock = asyncio.Lock()
    
    def _generate_connection_id(self) -> str:
        """生成唯一连接 ID"""
        self._connection_counter += 1
        return f"conn_{self._connection_counter}_{datetime.now().timestamp()}"
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
    ) -> ConnectionInfo:
        """
        注册新的 WebSocket 连接
        
        Args:
            websocket: WebSocket 连接对象
            user_id: 用户 ID
        
        Returns:
            ConnectionInfo: 连接信息
        """
        async with self._lock:
            connection_id = self._generate_connection_id()
            conn_info = ConnectionInfo(
                websocket=websocket,
                user_id=user_id,
                connection_id=connection_id,
                status=ConnectionStatus.CONNECTED,
            )
            
            # 添加到用户连接字典
            if user_id not in self._connections:
                self._connections[user_id] = {}
            self._connections[user_id][connection_id] = conn_info
            
            # 添加到连接映射
            self._connection_map[connection_id] = conn_info
            
            logger.info(f"WebSocket connected: user_id={user_id}, connection_id={connection_id}, "
                       f"total_connections={len(self._connection_map)}")
            
            return conn_info
    
    async def disconnect(self, connection_id: str) -> Optional[int]:
        """
        断开 WebSocket 连接
        
        Args:
            connection_id: 连接 ID
        
        Returns:
            int: 用户 ID，如果连接不存在返回 None
        """
        async with self._lock:
            conn_info = self._connection_map.pop(connection_id, None)
            
            if conn_info is None:
                return None
            
            user_id = conn_info.user_id
            
            # 从用户连接字典中移除
            if user_id in self._connections:
                self._connections[user_id].pop(connection_id, None)
                # 如果用户没有连接了，删除整个字典
                if not self._connections[user_id]:
                    del self._connections[user_id]
            
            conn_info.status = ConnectionStatus.DISCONNECTED
            
            logger.info(f"WebSocket disconnected: user_id={user_id}, connection_id={connection_id}, "
                       f"total_connections={len(self._connection_map)}")
            
            return user_id
    
    async def authenticate(self, connection_id: str) -> bool:
        """
        标记连接为已认证
        
        Args:
            connection_id: 连接 ID
        
        Returns:
            bool: 是否成功
        """
        conn_info = self._connection_map.get(connection_id)
        if conn_info:
            conn_info.status = ConnectionStatus.AUTHENTICATED
            conn_info.update_activity()
            logger.debug(f"WebSocket authenticated: connection_id={connection_id}")
            return True
        return False
    
    def is_authenticated(self, connection_id: str) -> bool:
        """检查连接是否已认证"""
        conn_info = self._connection_map.get(connection_id)
        return conn_info is not None and conn_info.status == ConnectionStatus.AUTHENTICATED
    
    def get_user_connections(self, user_id: int) -> List[ConnectionInfo]:
        """
        获取用户的所有连接
        
        Args:
            user_id: 用户 ID
        
        Returns:
            List[ConnectionInfo]: 连接列表
        """
        return list(self._connections.get(user_id, {}).values())
    
    def is_user_online(self, user_id: int) -> bool:
        """
        检查用户是否在线（有至少一个已认证的连接）
        
        Args:
            user_id: 用户 ID
        
        Returns:
            bool: 是否在线
        """
        connections = self._connections.get(user_id, {})
        return any(
            conn.status == ConnectionStatus.AUTHENTICATED
            for conn in connections.values()
        )
    
    def get_online_users(self) -> List[int]:
        """
        获取所有在线用户 ID
        
        Returns:
            List[int]: 在线用户 ID 列表
        """
        return [
            user_id for user_id, connections in self._connections.items()
            if any(conn.status == ConnectionStatus.AUTHENTICATED for conn in connections.values())
        ]
    
    async def send_to_connection(
        self,
        connection_id: str,
        message: dict,
    ) -> bool:
        """
        向指定连接发送消息
        
        Args:
            connection_id: 连接 ID
            message: 消息字典
        
        Returns:
            bool: 是否发送成功
        """
        conn_info = self._connection_map.get(connection_id)
        if conn_info is None:
            logger.warning(f"Connection not found: {connection_id}")
            return False
        
        try:
            await conn_info.websocket.send_json(message)
            conn_info.update_activity()
            return True
        except Exception as e:
            logger.error(f"Failed to send message to connection {connection_id}: {e}")
            return False
    
    async def send_to_user(
        self,
        user_id: int,
        message: dict,
    ) -> int:
        """
        向用户的所有连接发送消息（广播）
        
        Args:
            user_id: 用户 ID
            message: 消息字典
        
        Returns:
            int: 成功发送的连接数量
        """
        connections = self._connections.get(user_id, {})
        success_count = 0
        
        for conn_info in connections.values():
            if conn_info.status == ConnectionStatus.AUTHENTICATED:
                try:
                    await conn_info.websocket.send_json(message)
                    conn_info.update_activity()
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}, "
                               f"connection {conn_info.connection_id}: {e}")
        
        return success_count
    
    async def broadcast(
        self,
        message: dict,
        exclude_user_ids: Optional[Set[int]] = None,
    ) -> int:
        """
        向所有在线用户广播消息
        
        Args:
            message: 消息字典
            exclude_user_ids: 排除的用户 ID 集合
        
        Returns:
            int: 成功发送的连接数量
        """
        exclude_user_ids = exclude_user_ids or set()
        success_count = 0
        
        for user_id, connections in list(self._connections.items()):
            if user_id in exclude_user_ids:
                continue
            
            for conn_info in connections.values():
                if conn_info.status == ConnectionStatus.AUTHENTICATED:
                    try:
                        await conn_info.websocket.send_json(message)
                        conn_info.update_activity()
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to broadcast to user {user_id}, "
                                   f"connection {conn_info.connection_id}: {e}")
        
        return success_count
    
    def get_stats(self) -> dict:
        """
        获取连接统计信息
        
        Returns:
            dict: 统计信息
        """
        total_connections = len(self._connection_map)
        authenticated_connections = sum(
            1 for conn in self._connection_map.values()
            if conn.status == ConnectionStatus.AUTHENTICATED
        )
        online_users = len(self.get_online_users())
        
        return {
            "total_connections": total_connections,
            "authenticated_connections": authenticated_connections,
            "online_users": online_users,
            "users_with_connections": len(self._connections),
        }
    
    async def cleanup_stale_connections(self, timeout_seconds: int = 300) -> int:
        """
        清理超时的连接
        
        Args:
            timeout_seconds: 超时时间（秒）
        
        Returns:
            int: 清理的连接数量
        """
        # 此方法可用于清理异常断开但未正确关闭的连接
        # 在实际应用中，可以通过心跳机制检测
        pass


# 全局 WebSocket 管理器实例
websocket_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    """获取 WebSocket 管理器实例"""
    return websocket_manager
