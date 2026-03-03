"""
定时任务调度器服务
使用 APScheduler 实现定时任务管理
"""
import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from backend.config import settings


@dataclass
class TaskInfo:
    """任务信息数据类"""
    id: str
    user_id: int
    content: str
    cron: str
    natural_language: str
    enabled: bool
    created_at: str
    last_run: Optional[str] = None
    next_run: Optional[str] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "TaskInfo":
        """从字典创建"""
        return cls(**data)


class TaskStore:
    """任务存储管理 - JSON 文件存储"""
    
    def __init__(self, tasks_dir: str = None):
        self.tasks_dir = tasks_dir or settings.TASKS_DIR
        self._ensure_dir()
    
    def _ensure_dir(self):
        """确保目录存在"""
        os.makedirs(self.tasks_dir, exist_ok=True)
    
    def _get_user_file(self, user_id: int) -> str:
        """获取用户任务文件路径"""
        return os.path.join(self.tasks_dir, f"{user_id}.json")
    
    def load_user_tasks(self, user_id: int) -> List[TaskInfo]:
        """加载用户任务列表"""
        file_path = self._get_user_file(user_id)
        
        if not os.path.exists(file_path):
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [TaskInfo.from_dict(task) for task in data.get('tasks', [])]
        except (json.JSONDecodeError, KeyError):
            return []
    
    def save_user_tasks(self, user_id: int, tasks: List[TaskInfo]):
        """保存用户任务列表"""
        file_path = self._get_user_file(user_id)
        
        data = {
            'user_id': user_id,
            'tasks': [task.to_dict() for task in tasks]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_task(self, user_id: int, task: TaskInfo):
        """添加任务"""
        tasks = self.load_user_tasks(user_id)
        tasks.append(task)
        self.save_user_tasks(user_id, tasks)
    
    def update_task(self, user_id: int, task: TaskInfo) -> bool:
        """更新任务"""
        tasks = self.load_user_tasks(user_id)
        
        for i, t in enumerate(tasks):
            if t.id == task.id:
                tasks[i] = task
                self.save_user_tasks(user_id, tasks)
                return True
        
        return False
    
    def delete_task(self, user_id: int, task_id: str) -> bool:
        """删除任务"""
        tasks = self.load_user_tasks(user_id)
        
        for i, task in enumerate(tasks):
            if task.id == task_id:
                tasks.pop(i)
                self.save_user_tasks(user_id, tasks)
                return True
        
        return False
    
    def get_task(self, user_id: int, task_id: str) -> Optional[TaskInfo]:
        """获取单个任务"""
        tasks = self.load_user_tasks(user_id)
        
        for task in tasks:
            if task.id == task_id:
                return task
        
        return None


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler(
            jobstores={'default': MemoryJobStore()},
            executors={'default': ThreadPoolExecutor(20)},
            timezone='Asia/Shanghai'
        )
        self.task_store = TaskStore()
        self._task_callbacks: Dict[str, Callable] = {}  # 任务回调函数
        self._is_running = False
    
    def generate_task_id(self) -> str:
        """生成唯一任务 ID"""
        return f"task_{uuid.uuid4().hex[:12]}"
    
    def start(self):
        """启动调度器"""
        if not self._is_running:
            self.scheduler.start()
            self._is_running = True
    
    def shutdown(self, wait: bool = True):
        """关闭调度器"""
        if self._is_running:
            self.scheduler.shutdown(wait=wait)
            self._is_running = False
    
    def set_task_callback(self, callback: Callable):
        """
        设置任务执行回调函数
        回调函数签名: async def callback(user_id: int, task_id: str, content: str) -> Any
        """
        self._task_callbacks['default'] = callback
    
    async def _execute_task(self, user_id: int, task_id: str, content: str):
        """执行任务（内部方法）"""
        try:
            # 更新任务最后执行时间
            task = self.task_store.get_task(user_id, task_id)
            if task:
                task.last_run = datetime.now().isoformat()
                self.task_store.update_task(user_id, task)
            
            # 执行回调
            if 'default' in self._task_callbacks:
                callback = self._task_callbacks['default']
                if asyncio.iscoroutinefunction(callback):
                    await callback(user_id, task_id, content)
                else:
                    callback(user_id, task_id, content)
                    
        except Exception as e:
            print(f"Task execution error: user_id={user_id}, task_id={task_id}, error={e}")
    
    def add_task(self, user_id: int, content: str, cron: str, 
                 natural_language: str, enabled: bool = True) -> TaskInfo:
        """
        添加定时任务
        
        Args:
            user_id: 用户 ID
            content: 任务内容（执行时发送给 iFlow 的消息）
            cron: Cron 表达式
            natural_language: 自然语言描述
            enabled: 是否启用
        
        Returns:
            TaskInfo: 任务信息
        """
        # 生成唯一任务 ID
        task_id = self.generate_task_id()
        
        # 创建任务信息
        task = TaskInfo(
            id=task_id,
            user_id=user_id,
            content=content,
            cron=cron,
            natural_language=natural_language,
            enabled=enabled,
            created_at=datetime.now().isoformat()
        )
        
        # 保存到文件
        self.task_store.add_task(user_id, task)
        
        # 如果启用，添加到调度器
        if enabled:
            self._schedule_task(task)
        
        return task
    
    def _schedule_task(self, task: TaskInfo):
        """将任务添加到调度器"""
        try:
            # 解析 cron 表达式
            trigger = CronTrigger.from_crontab(task.cron, timezone='Asia/Shanghai')
            
            # 添加任务到调度器
            self.scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                id=task.id,
                args=[task.user_id, task.id, task.content],
                replace_existing=True
            )
            
            # 更新下次执行时间
            job = self.scheduler.get_job(task.id)
            if job and hasattr(job, 'next_run_time') and job.next_run_time:
                task.next_run = job.next_run_time.isoformat()
                self.task_store.update_task(task.user_id, task)
                
        except Exception as e:
            print(f"Failed to schedule task {task.id}: {e}")
    
    def remove_task(self, user_id: int, task_id: str) -> bool:
        """
        删除任务
        
        Args:
            user_id: 用户 ID
            task_id: 任务 ID
        
        Returns:
            bool: 是否删除成功
        """
        # 从调度器中移除
        try:
            self.scheduler.remove_job(task_id)
        except Exception:
            pass  # 任务可能不在调度器中
        
        # 从存储中删除
        return self.task_store.delete_task(user_id, task_id)
    
    def enable_task(self, user_id: int, task_id: str) -> bool:
        """启用任务"""
        task = self.task_store.get_task(user_id, task_id)
        
        if not task:
            return False
        
        task.enabled = True
        self.task_store.update_task(user_id, task)
        self._schedule_task(task)
        
        return True
    
    def disable_task(self, user_id: int, task_id: str) -> bool:
        """禁用任务"""
        task = self.task_store.get_task(user_id, task_id)
        
        if not task:
            return False
        
        task.enabled = False
        task.next_run = None
        self.task_store.update_task(user_id, task)
        
        # 从调度器中移除
        try:
            self.scheduler.remove_job(task_id)
        except Exception:
            pass
        
        return True
    
    def toggle_task(self, user_id: int, task_id: str) -> Optional[TaskInfo]:
        """切换任务启用状态"""
        task = self.task_store.get_task(user_id, task_id)
        
        if not task:
            return None
        
        if task.enabled:
            self.disable_task(user_id, task_id)
        else:
            self.enable_task(user_id, task_id)
        
        return self.task_store.get_task(user_id, task_id)
    
    def get_user_tasks(self, user_id: int) -> List[TaskInfo]:
        """获取用户所有任务"""
        tasks = self.task_store.load_user_tasks(user_id)
        
        # 更新下次执行时间
        for task in tasks:
            if task.enabled:
                job = self.scheduler.get_job(task.id)
                if job and hasattr(job, 'next_run_time') and job.next_run_time:
                    task.next_run = job.next_run_time.isoformat()
        
        return tasks
    
    def get_task(self, user_id: int, task_id: str) -> Optional[TaskInfo]:
        """获取单个任务"""
        return self.task_store.get_task(user_id, task_id)
    
    def reload_user_tasks(self, user_id: int):
        """
        重新加载用户任务到调度器
        用于服务重启后恢复任务
        """
        tasks = self.task_store.load_user_tasks(user_id)
        
        for task in tasks:
            if task.enabled:
                self._schedule_task(task)
    
    def reload_all_tasks(self):
        """
        重新加载所有用户任务到调度器
        用于服务重启后恢复所有任务
        """
        # 遍历任务目录下的所有 JSON 文件
        if not os.path.exists(self.task_store.tasks_dir):
            return
        
        for filename in os.listdir(self.task_store.tasks_dir):
            if filename.endswith('.json'):
                try:
                    user_id = int(filename[:-5])  # 去掉 .json 后缀
                    self.reload_user_tasks(user_id)
                except ValueError:
                    continue  # 跳过无效文件名
    
    def get_next_run_time(self, task_id: str) -> Optional[datetime]:
        """获取任务下次执行时间"""
        job = self.scheduler.get_job(task_id)
        return job.next_run_time if job else None


# 全局调度器实例
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


def start_scheduler():
    """启动调度器"""
    scheduler = get_scheduler()
    scheduler.start()
    # 重新加载所有任务
    scheduler.reload_all_tasks()


def shutdown_scheduler(wait: bool = True):
    """关闭调度器"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=wait)
