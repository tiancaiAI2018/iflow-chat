"""
iFlow 对话网页应用 - 目录列表路由

提供工作目录树结构 API，用于前端目录选择器
"""
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.models.schemas import ErrorResponse
from backend.services.auth import get_current_user
from backend.models.user import User


router = APIRouter()

# 工作目录根路径
WORKSPACE_ROOT = "/root/.iflow-bot/workspace"


class DirectoryNode(BaseModel):
    """目录节点模型"""
    name: str
    path: str
    children: Optional[List["DirectoryNode"]] = None


class DirectoryListResponse(BaseModel):
    """目录列表响应模型"""
    success: bool = True
    directories: List[DirectoryNode]
    root_path: str


def get_directory_tree(base_path: str, max_depth: int = 3, current_depth: int = 0) -> List[DirectoryNode]:
    """
    递归获取目录树结构
    
    Args:
        base_path: 基础路径
        max_depth: 最大递归深度
        current_depth: 当前递归深度
    
    Returns:
        List[DirectoryNode]: 目录节点列表
    """
    if current_depth >= max_depth:
        return []
    
    result = []
    
    try:
        entries = sorted(os.listdir(base_path))
    except PermissionError:
        return []
    except OSError:
        return []
    
    for entry in entries:
        # 跳过隐藏目录和文件
        if entry.startswith('.'):
            continue
        
        full_path = os.path.join(base_path, entry)
        
        # 只处理目录
        if os.path.isdir(full_path):
            node = DirectoryNode(
                name=entry,
                path=full_path,
                children=None
            )
            
            # 递归获取子目录
            if current_depth < max_depth - 1:
                children = get_directory_tree(full_path, max_depth, current_depth + 1)
                if children:
                    node.children = children
            
            result.append(node)
    
    return result


@router.get(
    "/",
    response_model=DirectoryListResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="获取目录树结构",
    description="获取工作目录下的目录树结构，用于目录选择器"
)
async def get_directories(
    current_user: User = Depends(get_current_user),
) -> DirectoryListResponse:
    """
    获取目录树结构
    
    返回 /root/.iflow-bot/workspace 下的目录树结构，
    支持递归获取子目录（最多 3 层深度）
    """
    # 检查工作目录是否存在
    if not os.path.exists(WORKSPACE_ROOT):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工作目录不存在: {WORKSPACE_ROOT}"
        )
    
    if not os.path.isdir(WORKSPACE_ROOT):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"路径不是目录: {WORKSPACE_ROOT}"
        )
    
    # 获取目录树
    directories = get_directory_tree(WORKSPACE_ROOT)
    
    return DirectoryListResponse(
        success=True,
        directories=directories,
        root_path=WORKSPACE_ROOT,
    )


@router.get(
    "/subdirectory",
    response_model=DirectoryListResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="获取子目录树结构",
    description="获取指定路径下的子目录树结构"
)
async def get_subdirectories(
    path: str,
    current_user: User = Depends(get_current_user),
) -> DirectoryListResponse:
    """
    获取子目录树结构
    
    - **path**: 要获取子目录的路径（必须在 workspace 范围内）
    
    返回指定路径下的目录结构
    """
    # 安全检查：路径必须在 workspace 范围内
    normalized_path = os.path.normpath(path)
    if not normalized_path.startswith(WORKSPACE_ROOT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="路径必须在工作目录范围内"
        )
    
    # 检查路径是否存在
    if not os.path.exists(normalized_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"目录不存在: {normalized_path}"
        )
    
    if not os.path.isdir(normalized_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"路径不是目录: {normalized_path}"
        )
    
    # 获取目录树
    directories = get_directory_tree(normalized_path)
    
    return DirectoryListResponse(
        success=True,
        directories=directories,
        root_path=normalized_path,
    )


# 更新 forward reference
DirectoryNode.model_rebuild()
