"""
iFlow 对话网页应用 - 定时任务路由

提供定时任务的创建、查询、删除、启用/禁用等 API
"""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.models.user import User
from backend.models.schemas import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskCreateResponse,
    TaskDeleteResponse,
    TaskToggleResponse,
    ErrorResponse,
)
from backend.services.auth import get_current_user
from backend.services.scheduler import get_scheduler, TaskInfo
from backend.services.task_parser import get_task_parser


router = APIRouter()


def task_info_to_response(task: TaskInfo) -> TaskResponse:
    """将 TaskInfo 转换为 TaskResponse"""
    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        content=task.content,
        cron=task.cron,
        natural_language=task.natural_language,
        enabled=task.enabled,
        created_at=task.created_at,
        last_run=task.last_run,
        next_run=task.next_run
    )


@router.get(
    "",
    response_model=TaskListResponse,
    responses={
        401: {"model": ErrorResponse},
    },
    summary="获取任务列表",
    description="获取当前用户的所有定时任务"
)
async def get_tasks(
    current_user: User = Depends(get_current_user)
) -> TaskListResponse:
    """
    获取任务列表接口
    
    返回当前用户的所有定时任务，包括启用和禁用的任务
    """
    scheduler = get_scheduler()
    tasks = scheduler.get_user_tasks(current_user.id)
    
    return TaskListResponse(
        success=True,
        tasks=[task_info_to_response(task) for task in tasks]
    )


@router.post(
    "",
    response_model=TaskCreateResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
    summary="创建任务",
    description="使用自然语言创建定时任务（AI 自动解析时间）"
)
async def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user)
) -> TaskCreateResponse:
    """
    创建任务接口
    
    - **description**: 自然语言描述，如 "每天早上9点提醒我查看股票"
    
    系统会自动解析自然语言，提取时间信息和任务内容，生成对应的 Cron 表达式
    """
    # 解析自然语言
    parser = get_task_parser()
    parsed_task = await parser.parse(task_data.description)
    
    if not parsed_task.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=parsed_task.error or "无法解析任务描述"
        )
    
    # 验证 Cron 表达式
    if not parser.validate_cron(parsed_task.cron_expression):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="生成的 Cron 表达式无效"
        )
    
    # 创建任务
    scheduler = get_scheduler()
    task = scheduler.add_task(
        user_id=current_user.id,
        content=parsed_task.content,
        cron=parsed_task.cron_expression,
        natural_language=task_data.description,
        enabled=True
    )
    
    return TaskCreateResponse(
        success=True,
        task=task_info_to_response(task),
        message="任务创建成功"
    )


@router.delete(
    "/{task_id}",
    response_model=TaskDeleteResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="删除任务",
    description="删除指定的定时任务"
)
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> TaskDeleteResponse:
    """
    删除任务接口
    
    - **task_id**: 任务 ID
    """
    scheduler = get_scheduler()
    
    # 检查任务是否存在
    task = scheduler.get_task(current_user.id, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 删除任务
    success = scheduler.remove_task(current_user.id, task_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除任务失败"
        )
    
    return TaskDeleteResponse(
        success=True,
        message="任务删除成功"
    )


@router.put(
    "/{task_id}/toggle",
    response_model=TaskToggleResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="切换任务状态",
    description="启用或禁用指定的定时任务"
)
async def toggle_task(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> TaskToggleResponse:
    """
    切换任务状态接口
    
    - **task_id**: 任务 ID
    
    启用的任务会被禁用，禁用的任务会被启用
    """
    scheduler = get_scheduler()
    
    # 检查任务是否存在
    task = scheduler.get_task(current_user.id, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 切换状态
    updated_task = scheduler.toggle_task(current_user.id, task_id)
    
    if not updated_task:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="切换任务状态失败"
        )
    
    return TaskToggleResponse(
        success=True,
        task=task_info_to_response(updated_task),
        message=f"任务已{'启用' if updated_task.enabled else '禁用'}"
    )
