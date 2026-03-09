"""
ACP (Agent Communication Protocol) 端口管理路由

提供 ACP 端口查看、状态监控、连接池状态等 API
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.auth import get_current_user
from backend.models.user import User
from backend.services.iflow_client import IFlowClientService

router = APIRouter()


class KillPortRequest(BaseModel):
    """Kill 端口请求"""
    port: int


class KillPortResponse(BaseModel):
    """Kill 端口响应"""
    success: bool
    message: str
    port: int


class ACPInfoResponse(BaseModel):
    """ACP 端口信息响应"""
    user_id: int
    ports: list
    current_port: Optional[int]
    total_ports: int
    last_used: Optional[Dict[str, Any]] = None


class ACPStatusResponse(BaseModel):
    """ACP 全局状态响应"""
    user_ports: dict
    used_ports: list
    total_used: int
    active_processes: int
    last_used_ports: dict = {}


class ConnectionPoolStatusResponse(BaseModel):
    """连接池状态响应"""
    total_connections: int
    connections: list


@router.get(
    "/my-ports",
    response_model=ACPInfoResponse,
    summary="获取当前用户的 ACP 端口信息",
    description="返回用户当前绑定的 ACP 端口列表，栈顶为当前正在使用的端口"
)
async def get_my_acp_ports(
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户的 ACP 端口信息
    
    返回：
    - user_id: 用户 ID
    - ports: 端口列表（栈顶为当前使用的端口）
    - current_port: 当前使用的端口
    - total_ports: 使用的端口总数
    """
    return IFlowClientService.get_user_acp_info(current_user.id)


@router.get(
    "/status",
    response_model=ACPStatusResponse,
    summary="获取 ACP 全局状态（调试用）",
    description="返回所有用户的 ACP 端口使用情况"
)
async def get_acp_status(
    current_user: User = Depends(get_current_user),
):
    """
    获取 ACP 全局状态
    
    返回：
    - user_ports: 所有用户的端口映射
    - used_ports: 已使用的端口列表
    - total_used: 已使用端口总数
    - active_processes: 活跃进程数
    """
    return IFlowClientService.get_all_acp_status()


@router.get(
    "/pool-status",
    response_model=ConnectionPoolStatusResponse,
    summary="获取连接池状态",
    description="返回当前连接池中所有连接的状态"
)
async def get_connection_pool_status(
    current_user: User = Depends(get_current_user),
):
    """
    获取连接池状态
    
    返回：
    - total_connections: 总连接数
    - connections: 连接详情列表（user_id, conversation_id, port, idle_seconds 等）
    """
    from backend.services.connection_pool import get_connection_pool
    pool = get_connection_pool()
    return pool.get_stats()


@router.post(
    "/kill-port",
    response_model=KillPortResponse,
    summary="Kill 指定的 ACP 端口",
    description="停止并清理指定的 ACP 进程，只能 kill 当前用户非活跃的端口"
)
async def kill_acp_port(
    request: KillPortRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Kill 指定的 ACP 端口
    
    只能 kill：
    1. 属于当前用户的端口
    2. 非当前活跃的端口（栈顶端口不能 kill）
    
    Args:
        request: 包含 port 的请求体
        
    Returns:
        KillPortResponse: 操作结果
    """
    user_id = current_user.id
    port = request.port
    
    # 获取用户的端口信息
    acp_info = IFlowClientService.get_user_acp_info(user_id)
    user_ports = acp_info.get("ports", [])
    current_port = acp_info.get("current_port")
    
    # 检查端口是否属于当前用户
    if port not in user_ports:
        raise HTTPException(
            status_code=403,
            detail=f"端口 {port} 不属于当前用户"
        )
    
    # 检查是否是当前活跃端口
    if port == current_port:
        raise HTTPException(
            status_code=400,
            detail=f"端口 {port} 是当前活跃端口，无法 kill"
        )
    
    try:
        # 停止 ACP 进程
        await IFlowClientService._stop_acp_process(port)
        
        # 从用户端口栈中移除
        IFlowClientService._remove_user_port(user_id, port)
        
        return KillPortResponse(
            success=True,
            message=f"已成功停止端口 {port} 的 ACP 进程",
            port=port
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"停止端口 {port} 失败: {str(e)}"
        )
