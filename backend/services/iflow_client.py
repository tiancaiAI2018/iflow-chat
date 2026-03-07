"""
iFlow SDK 封装服务
提供流式对话处理、工具调用消息解析、连接管理、错误恢复等功能
支持系统提示词注入，用于定时任务意图识别
"""
import asyncio
import logging
import json
import re
import os
import socket
import hashlib
from typing import AsyncGenerator, Optional, Callable, Any, Dict
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

# iFlow SDK 导入
from iflow_sdk import (
    IFlowClient as SDKClient,
    IFlowOptions,
    AssistantMessage,
    ToolCallMessage,
    TaskFinishMessage,
    ToolCallStatus,
    StopReason,
)
from iflow_sdk.types import ToolResultMessage

from backend.config import settings

logger = logging.getLogger(__name__)


# ==================== 端口管理 ====================

# 基础端口，用于 mybot 目录（已有进程）
BASE_PORT = 8090
# 动态端口范围起始
DYNAMIC_PORT_START = 8091
DYNAMIC_PORT_END = 8100

# 工作目录到端口的映射
_cwd_port_map: Dict[str, int] = {}
# 已使用的端口集合
_used_ports: set = {BASE_PORT}  # 8090 已被 mybot 进程占用

# 全局锁，用于保护 os.chdir 操作（进程级全局状态）
_cwd_lock = asyncio.Lock()


def _get_port_for_cwd(cwd: str) -> int:
    """
    根据工作目录获取对应的端口
    
    对于 mybot 目录使用固定的 8090 端口（已有进程）
    对于其他目录，根据目录路径哈希分配动态端口
    
    Args:
        cwd: 工作目录路径
    
    Returns:
        int: 分配的端口号
    """
    global _cwd_port_map, _used_ports
    
    # 标准化路径
    normalized_cwd = os.path.abspath(cwd)
    
    # 如果是 mybot 目录，使用基础端口
    if normalized_cwd.endswith('/mybot') or normalized_cwd == '/root/.iflow-bot/workspace/mybot':
        return BASE_PORT
    
    # 如果已经映射过，直接返回
    if normalized_cwd in _cwd_port_map:
        return _cwd_port_map[normalized_cwd]
    
    # 根据路径哈希分配端口
    hash_val = int(hashlib.md5(normalized_cwd.encode()).hexdigest(), 16)
    
    # 在动态端口范围内查找可用端口
    for offset in range(DYNAMIC_PORT_END - DYNAMIC_PORT_START + 1):
        port = DYNAMIC_PORT_START + (hash_val + offset) % (DYNAMIC_PORT_END - DYNAMIC_PORT_START + 1)
        if port not in _used_ports:
            _cwd_port_map[normalized_cwd] = port
            _used_ports.add(port)
            logger.info(f"Assigned port {port} for working directory: {normalized_cwd}")
            return port
    
    # 如果所有端口都被占用，抛出异常
    raise RuntimeError(f"No available ports for working directory: {normalized_cwd}")


def _is_port_available(port: int) -> bool:
    """
    检查端口是否可用（未被占用）
    
    Args:
        port: 端口号
    
    Returns:
        bool: 是否可用
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            return result != 0  # 如果连接失败（端口未被占用），返回 True
    except Exception:
        return False


# ==================== 系统提示词 ====================

# 定时任务意图识别系统提示词
SCHEDULE_TASK_SYSTEM_PROMPT = """
你是一个智能助手，具有创建定时任务的能力。

当用户表达想要创建定时任务/提醒/周期性任务时，请识别并返回特定格式的 JSON。

【识别关键词】
- "提醒我..."、"定时..."、"每天..."、"每周..."、"每月..."
- "每隔...分钟/小时..."、"周期性..."
- "到时间..."、"到时候..."

【返回格式】
如果用户意图是创建定时任务，请在响应的最后返回以下 JSON 格式：
```json
{"action": "create_task", "description": "用户的原始描述"}
```

【示例】
用户: "每天早上9点提醒我查看股票"
助手: 好的，我来帮你创建一个每天早上9点的提醒任务。
```json
{"action": "create_task", "description": "每天早上9点提醒我查看股票"}
```

用户: "每周一上午10点发送周报"
助手: 已为你创建每周一上午10点的定时任务。
```json
{"action": "create_task", "description": "每周一上午10点发送周报"}
```

用户: "每隔30分钟检查一次服务器状态"
助手: 好的，我将创建一个每隔30分钟的定时任务。
```json
{"action": "create_task", "description": "每隔30分钟检查一次服务器状态"}
```

【注意】
1. 只有当用户明确表达创建定时任务/提醒的意图时才返回 JSON
2. 普通对话不需要返回 JSON
3. JSON 必须放在响应的最后
4. description 字段保留用户的原始描述，不要修改
"""

# 前缀消息，用于注入系统提示词
SYSTEM_PROMPT_PREFIX = "[系统指令]\n" + SCHEDULE_TASK_SYSTEM_PROMPT + "\n[用户消息]\n"


class MessageType(Enum):
    """消息类型枚举"""
    TEXT = "text"              # 文本消息
    TOOL_CALL = "tool_call"    # 工具调用
    TASK_FINISH = "task_finish"  # 任务完成
    ERROR = "error"            # 错误消息


@dataclass
class ChatMessage:
    """聊天消息数据结构"""
    type: MessageType
    content: str = ""
    is_delta: bool = False      # 是否为增量消息
    is_finished: bool = False   # 是否完成
    
    # 工具调用相关
    tool_id: Optional[str] = None  # 工具调用 ID
    tool_name: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    tool_status: Optional[str] = None  # pending, in_progress, completed, failed
    tool_result: Optional[Any] = None
    tool_error: Optional[str] = None
    
    # 任务完成相关
    stop_reason: Optional[str] = None


class IFlowClientService:
    """
    iFlow SDK 封装服务
    提供 WebSocket 连接管理、流式对话处理、工具调用消息解析、自动重连
    包含服务可用性检测和错误恢复
    支持 ACP 进程手动管理（带 --stream 参数）
    """
    
    # ACP 进程管理类属性
    _port_processes: Dict[int, asyncio.subprocess.Process] = {}  # port -> process
    _user_ports: Dict[int, list] = {}  # user_id -> [port_new, port_old, ...] 端口栈
    _used_ports: set = set()  # 已使用的端口集合
    _lock: asyncio.Lock = asyncio.Lock()  # 端口分配锁
    
    def __init__(
        self,
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
        max_reconnect_attempts: int = 5,
        reconnect_base_delay: float = 1.0,
        health_check_interval: float = 60.0,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        初始化 iFlow 客户端服务
        
        Args:
            cwd: 工作目录，默认为 /root/.iflow-bot/workspace
            timeout: 超时时间（秒），默认使用配置中的超时时间
            max_reconnect_attempts: 最大重连尝试次数
            reconnect_base_delay: 重连基础延迟（秒）
            health_check_interval: 健康检查间隔（秒）
            session_id: iFlow 会话 ID，用于保持会话上下文
            user_id: 用户 ID，用于端口栈管理
        """
        self.cwd = cwd or "/root/.iflow-bot/workspace"
        self.timeout = timeout or settings.IFLOW_TIMEOUT
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_base_delay = reconnect_base_delay
        self.health_check_interval = health_check_interval
        self.session_id = session_id
        self.user_id = user_id or 0  # 默认用户 ID 为 0
        self._client: Optional[SDKClient] = None
        self._options: Optional[IFlowOptions] = None
        self._is_connected = False
        self._connection_errors: list = []  # 记录连接错误历史
        self._last_connect_time: Optional[datetime] = None
        self._is_service_available = True  # 服务可用性标志
        self._consecutive_failures = 0  # 连续失败次数
        self._service_unavailable_threshold = 3  # 判定服务不可用的连续失败阈值
        
        # 端口和 URL 将在 connect 时动态分配
        self._port: Optional[int] = None
        self._url: Optional[str] = None
    
    async def connect(self) -> None:
        """
        建立 WebSocket 连接
        使用 ACP 进程手动管理模式：
        1. 查找可用端口
        2. 启动 ACP 进程（带 --stream 参数）
        3. 端口入栈
        4. SDK 连接（auto_start_process=False）
        支持自动重试
        
        注意：由于 os.chdir 是进程级全局操作，使用 _cwd_lock 锁保护以避免并发问题
        """
        if self._is_connected and self._client:
            logger.debug("Already connected to iFlow service")
            return
        
        last_error = None
        for attempt in range(self.max_reconnect_attempts):
            try:
                # 步骤 1: 查找可用端口
                port = await self._find_available_port(self.user_id)
                logger.info(f"Found available port {port} for user {self.user_id}")
                
                # 步骤 2: 启动 ACP 进程
                process = await self._start_acp_process(port)
                logger.info(f"Started ACP process on port {port}")
                
                # 步骤 3: 端口入栈
                self._push_user_port(self.user_id, port)
                
                # 设置端口和 URL
                self._port = port
                self._url = f"ws://localhost:{port}/acp"
                
                # 步骤 4: SDK 连接配置（auto_start_process=False，手动管理）
                self._options = IFlowOptions(
                    url=self._url,
                    auto_start_process=False,  # 关键：手动管理 ACP 进程
                    cwd=self.cwd,
                    timeout=self.timeout,
                    session_id=self.session_id,
                )
                
                # 使用全局锁保护目录切换操作（进程级全局状态）
                async with _cwd_lock:
                    # 保存原来的工作目录
                    original_cwd = os.getcwd()
                    try:
                        # 切换到目标工作目录（iflow ACP 进程将在此目录启动）
                        os.chdir(self.cwd)
                        logger.debug(f"Changed working directory to: {self.cwd}")
                        
                        # 创建并连接 SDKClient
                        self._client = SDKClient(options=self._options)
                        await self._client.__aenter__()
                    finally:
                        # 恢复原来的工作目录
                        os.chdir(original_cwd)
                        logger.debug(f"Restored working directory to: {original_cwd}")
                
                self._is_connected = True
                self._last_connect_time = datetime.now()
                self._connection_errors = []  # 清空错误历史
                self._record_success()  # 记录成功连接
                
                # 更新 session_id（首次连接时由服务器生成）
                if hasattr(self._client, '_session_id') and self._client._session_id:
                    self.session_id = self._client._session_id
                    logger.info(f"Connected to iFlow service with cwd={self.cwd}, port={port}, user_id={self.user_id}, session_id={self.session_id}")
                else:
                    logger.info(f"Connected to iFlow service with cwd={self.cwd}, port={port}, user_id={self.user_id}")
                return
                
            except Exception as e:
                last_error = e
                self._connection_errors.append({
                    "time": datetime.now().isoformat(),
                    "error": str(e),
                    "attempt": attempt + 1,
                })
                self._record_failure(str(e))  # 记录失败
                
                # 清理已分配的资源
                if hasattr(self, '_port') and self._port:
                    await self._stop_acp_process(self._port)
                    self._remove_user_port(self.user_id, self._port)
                    self._port = None
                    self._url = None
                
                if attempt < self.max_reconnect_attempts - 1:
                    delay = self.reconnect_base_delay * (2 ** attempt)  # 指数退避
                    logger.warning(
                        f"Connection attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
        
        # 所有尝试都失败
        logger.error(f"Failed to connect to iFlow service after {self.max_reconnect_attempts} attempts")
        self._is_connected = False
        raise ConnectionError(
            f"Failed to connect to iFlow service after {self.max_reconnect_attempts} attempts: {last_error}"
        )
    
    async def disconnect(self) -> None:
        """
        断开 WebSocket 连接
        """
        if self._client and self._is_connected:
            try:
                await self._client.__aexit__(None, None, None)
                logger.info("Disconnected from iFlow service")
            except Exception as e:
                logger.error(f"Error disconnecting from iFlow service: {e}")
            finally:
                self._client = None
                self._is_connected = False
    
    # ==================== ACP 端口管理方法 ====================
    
    @classmethod
    def _is_port_available(cls, port: int) -> bool:
        """
        检查端口是否可用（未被占用）
        
        Args:
            port: 端口号
        
        Returns:
            bool: 是否可用
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                return result != 0  # 如果连接失败（端口未被占用），返回 True
        except Exception:
            return False
    
    @classmethod
    async def _find_available_port(cls, user_id: int) -> int:
        """
        查找可用端口
        基于用户 ID 和端口范围查找可用端口，支持重试机制
        
        Args:
            user_id: 用户 ID
        
        Returns:
            int: 可用端口号
        
        Raises:
            RuntimeError: 当无法分配端口时抛出
        """
        async with cls._lock:
            for i in range(settings.ACP_MAX_PORT_RETRIES):
                # 基于用户 ID 和尝试次数计算端口
                port_range = settings.ACP_PORT_END - settings.ACP_PORT_START + 1
                base = settings.ACP_PORT_START + ((user_id * 10 + i) % port_range)
                port = base
                
                if port not in cls._used_ports and cls._is_port_available(port):
                    cls._used_ports.add(port)
                    logger.info(f"Assigned port {port} for user {user_id} (attempt {i + 1})")
                    return port
                
                logger.debug(f"Port {port} not available for user {user_id}, retrying...")
            
            raise RuntimeError(f"系统繁忙，无法为用户 {user_id} 分配端口，请稍后重试")
    
    @classmethod
    def _push_user_port(cls, user_id: int, port: int) -> None:
        """
        将端口压入用户端口栈（栈顶为最新端口）
        
        Args:
            user_id: 用户 ID
            port: 端口号
        """
        if user_id not in cls._user_ports:
            cls._user_ports[user_id] = []
        cls._user_ports[user_id].insert(0, port)  # 栈顶插入
        logger.debug(f"Pushed port {port} to user {user_id} stack: {cls._user_ports[user_id]}")
    
    @classmethod
    def _pop_user_port(cls, user_id: int, port: int) -> bool:
        """
        从用户端口栈中移除指定端口
        
        Args:
            user_id: 用户 ID
            port: 端口号
        
        Returns:
            bool: 是否成功移除
        """
        if user_id in cls._user_ports and port in cls._user_ports[user_id]:
            cls._user_ports[user_id].remove(port)
            cls._used_ports.discard(port)
            logger.debug(f"Popped port {port} from user {user_id} stack: {cls._user_ports[user_id]}")
            return True
        return False
    
    @classmethod
    def _get_user_ports(cls, user_id: int) -> list:
        """
        获取用户端口栈（栈顶为最新端口）
        
        Args:
            user_id: 用户 ID
        
        Returns:
            list: 端口列表，栈顶在索引 0
        """
        return cls._user_ports.get(user_id, []).copy()
    
    @classmethod
    def _remove_user_port(cls, user_id: int, port: int) -> None:
        """
        从用户端口栈中移除指定端口，并清理已使用端口集合
        
        Args:
            user_id: 用户 ID
            port: 端口号
        """
        if user_id in cls._user_ports:
            if port in cls._user_ports[user_id]:
                cls._user_ports[user_id].remove(port)
                logger.debug(f"Removed port {port} from user {user_id} stack")
            # 如果端口栈为空，删除用户条目
            if not cls._user_ports[user_id]:
                del cls._user_ports[user_id]
                logger.debug(f"Removed empty port stack for user {user_id}")
        cls._used_ports.discard(port)
        logger.debug(f"Removed port {port} from used ports")
    
    @classmethod
    async def _start_acp_process(cls, port: int) -> asyncio.subprocess.Process:
        """
        启动 ACP 进程
        使用 asyncio.create_subprocess_exec 启动 'iflow --experimental-acp --stream --port {port}' 命令
        
        Args:
            port: 端口号
        
        Returns:
            asyncio.subprocess.Process: 启动的进程对象
        
        Raises:
            TimeoutError: 当进程启动超时时抛出
            RuntimeError: 当进程启动失败时抛出
        """
        cmd = [
            "iflow",
            "--experimental-acp",
            "--stream",
            "--port", str(port),
        ]
        
        logger.info(f"Starting ACP process on port {port}: {' '.join(cmd)}")
        
        try:
            # 启动进程
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            
            logger.info(f"ACP process started with PID {process.pid} on port {port}")
            
            # 保存进程到管理字典
            cls._port_processes[port] = process
            
            # 等待进程就绪（通过检查端口是否被占用）
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < settings.ACP_STARTUP_TIMEOUT:
                # 检查进程是否还在运行
                if process.returncode is not None:
                    raise RuntimeError(f"ACP process exited prematurely with code {process.returncode}")
                
                # 检查端口是否被占用（表示服务已启动）
                if not cls._is_port_available(port):
                    logger.info(f"ACP process on port {port} is ready")
                    return process
                
                await asyncio.sleep(0.1)
            
            # 超时，终止进程并清理
            logger.error(f"ACP process on port {port} startup timeout after {settings.ACP_STARTUP_TIMEOUT}s")
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass
            
            # 清理
            cls._port_processes.pop(port, None)
            cls._used_ports.discard(port)
            
            raise TimeoutError(f"ACP process startup timeout after {settings.ACP_STARTUP_TIMEOUT} seconds")
            
        except Exception as e:
            # 清理
            cls._port_processes.pop(port, None)
            cls._used_ports.discard(port)
            
            if isinstance(e, (TimeoutError, RuntimeError)):
                raise
            raise RuntimeError(f"Failed to start ACP process on port {port}: {e}")
    
    @classmethod
    async def _stop_acp_process(cls, port: int) -> None:
        """
        停止 ACP 进程
        先 terminate 优雅终止，超时后 kill 强制终止，清理 _port_processes 字典
        
        Args:
            port: 端口号
        """
        process = cls._port_processes.get(port)
        
        if process is None:
            logger.debug(f"No ACP process found on port {port}")
            return
        
        logger.info(f"Stopping ACP process on port {port} (PID: {process.pid})")
        
        try:
            # 检查进程是否还在运行
            if process.returncode is not None:
                logger.debug(f"ACP process on port {port} already terminated with code {process.returncode}")
            else:
                # 先尝试优雅终止
                try:
                    process.terminate()
                    # 等待进程退出（最多2秒）
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                    logger.info(f"ACP process on port {port} terminated gracefully")
                except (asyncio.TimeoutError, ProcessLookupError):
                    # 优雅终止超时，强制 kill
                    try:
                        process.kill()
                        await process.wait()
                        logger.info(f"ACP process on port {port} killed forcefully")
                    except ProcessLookupError:
                        logger.debug(f"ACP process on port {port} already exited")
            
        except Exception as e:
            logger.error(f"Error stopping ACP process on port {port}: {e}")
        finally:
            # 清理管理字典
            cls._port_processes.pop(port, None)
            cls._used_ports.discard(port)
            logger.debug(f"Cleaned up port {port} from process management")
    
    async def reconnect(self) -> bool:
        """
        重新连接
        
        Returns:
            bool: 是否重连成功
        """
        try:
            await self.disconnect()
            await self.connect()
            return True
        except Exception as e:
            logger.error(f"Reconnect failed: {e}")
            return False
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._is_connected and self._client is not None
    
    def get_connection_errors(self) -> list:
        """
        获取连接错误历史
        
        Returns:
            list: 错误历史列表
        """
        return self._connection_errors.copy()
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        获取连接状态信息
        
        Returns:
            Dict: 状态信息
        """
        return {
            "is_connected": self.is_connected,
            "is_service_available": self._is_service_available,
            "cwd": self.cwd,
            "port": getattr(self, '_port', BASE_PORT),
            "url": getattr(self, '_url', f"ws://localhost:{BASE_PORT}/acp"),
            "last_connect_time": self._last_connect_time.isoformat() if self._last_connect_time else None,
            "error_count": len(self._connection_errors),
            "consecutive_failures": self._consecutive_failures,
            "last_error": self._connection_errors[-1] if self._connection_errors else None,
        }
    
    def _record_failure(self, error: str):
        """
        记录失败并更新服务可用性状态
        
        Args:
            error: 错误信息
        """
        self._consecutive_failures += 1
        
        if self._consecutive_failures >= self._service_unavailable_threshold:
            if self._is_service_available:
                logger.error(
                    f"iFlow service marked as unavailable after {self._consecutive_failures} consecutive failures"
                )
            self._is_service_available = False
    
    def _record_success(self):
        """记录成功并重置失败计数"""
        self._consecutive_failures = 0
        self._is_service_available = True
    
    @property
    def is_service_available(self) -> bool:
        """检查服务是否可用"""
        return self._is_service_available
    
    async def _on_task_finish(self) -> None:
        """
        任务完成时的回调方法
        智能判断是否断开旧 ACP 进程：
        - 栈长度=1：不断开（当前正在使用的连接）
        - 栈长度>1且当前端口是栈顶：不断开
        - 栈长度>1且当前端口不是栈顶：断开该进程并从栈中移除
        
        这样可以确保平滑过渡，旧连接的任务完成后自动清理资源。
        """
        if self._port is None:
            logger.debug(f"User {self.user_id}: _on_task_finish called but _port is None")
            return
        
        user_ports = self._get_user_ports(self.user_id)
        
        # 如果用户端口栈为空，不做任何操作
        if not user_ports:
            logger.debug(f"User {self.user_id}: No ports in stack, skipping disconnect")
            return
        
        # 如果栈长度为1，不断开（当前正在使用的连接）
        if len(user_ports) == 1:
            logger.debug(f"User {self.user_id}: Only one port in stack ({self._port}), keeping connection")
            return
        
        # 获取栈顶端口
        stack_top_port = user_ports[0]
        
        # 如果当前端口是栈顶，不断开
        if self._port == stack_top_port:
            logger.debug(f"User {self.user_id}: Current port {self._port} is stack top, keeping connection")
            return
        
        # 当前端口不是栈顶，需要断开旧进程
        logger.info(f"User {self.user_id}: Current port {self._port} is not stack top ({stack_top_port}), disconnecting old process")
        
        try:
            # 停止 ACP 进程
            await self._stop_acp_process(self._port)
            # 从用户端口栈中移除
            self._remove_user_port(self.user_id, self._port)
            logger.info(f"User {self.user_id}: Successfully disconnected old process on port {self._port}")
        except Exception as e:
            logger.error(f"User {self.user_id}: Error disconnecting old process on port {self._port}: {e}")
    
    async def query_stream(
        self,
        message: str,
        on_tool_call: Optional[Callable[[ChatMessage], None]] = None,
        auto_reconnect: bool = True,
        enable_task_detection: bool = True,
    ) -> AsyncGenerator[ChatMessage, None]:
        """
        流式查询处理
        
        Args:
            message: 用户消息
            on_tool_call: 工具调用回调函数
            auto_reconnect: 是否在连接断开时自动重连
            enable_task_detection: 是否启用定时任务意图检测（注入系统提示词）
        
        Yields:
            ChatMessage: 解析后的消息
        """
        if not self.is_connected:
            if auto_reconnect:
                try:
                    await self.connect()
                except Exception as e:
                    yield ChatMessage(
                        type=MessageType.ERROR,
                        content=f"Failed to connect to iFlow service: {str(e)}"
                    )
                    return
            else:
                yield ChatMessage(
                    type=MessageType.ERROR,
                    content="Not connected to iFlow service"
                )
                return
        
        if not self._client:
            yield ChatMessage(
                type=MessageType.ERROR,
                content="iFlow client not initialized"
            )
            return
        
        try:
            # 如果启用任务检测，注入系统提示词
            actual_message = message
            if enable_task_detection:
                actual_message = SYSTEM_PROMPT_PREFIX + message
            
            # 发送消息
            await self._client.send_message(actual_message)
            logger.debug(f"Sent message: {message[:50]}...")
            
            # 接收并处理消息
            async for msg in self._client.receive_messages():
                # 处理 AssistantMessage（文本消息）
                if isinstance(msg, AssistantMessage):
                    yield ChatMessage(
                        type=MessageType.TEXT,
                        content=msg.chunk.text,
                        is_delta=True,
                        is_finished=False,
                    )
                
                # 处理 ToolCallMessage（工具调用开始）
                elif isinstance(msg, ToolCallMessage):
                    tool_msg = self._parse_tool_call(msg)
                    
                    # 调用回调
                    if on_tool_call:
                        on_tool_call(tool_msg)
                    
                    yield tool_msg
                
                # 处理 ToolResultMessage（工具调用结果/更新）
                elif isinstance(msg, ToolResultMessage):
                    tool_msg = self._parse_tool_result(msg)
                    
                    # 调用回调
                    if on_tool_call:
                        on_tool_call(tool_msg)
                    
                    yield tool_msg
                
                # 处理 TaskFinishMessage（任务完成）
                elif isinstance(msg, TaskFinishMessage):
                    yield ChatMessage(
                        type=MessageType.TASK_FINISH,
                        is_finished=True,
                        stop_reason=msg.stop_reason.value if msg.stop_reason else None,
                    )
                    
                    # 任务完成时，智能判断是否断开旧 ACP 进程
                    await self._on_task_finish()
                    
                    break  # 结束消息循环
            
            # 发送完成标记
            yield ChatMessage(
                type=MessageType.TEXT,
                content="",
                is_delta=False,
                is_finished=True,
            )
            
            # 记录查询成功
            self._record_success()
            
        except asyncio.TimeoutError:
            logger.error("Query timeout")
            self._record_failure("Query timeout")
            yield ChatMessage(
                type=MessageType.ERROR,
                content="Query timeout, please try again"
            )
        except ConnectionError as e:
            logger.error(f"Connection error during query: {e}")
            self._is_connected = False
            self._record_failure(str(e))
            self._connection_errors.append({
                "time": datetime.now().isoformat(),
                "error": str(e),
                "type": "query_connection_error",
            })
            yield ChatMessage(
                type=MessageType.ERROR,
                content=f"Connection lost: {str(e)}. Please try again."
            )
        except Exception as e:
            logger.error(f"Error during query: {e}")
            # 检查是否是连接相关问题
            if "connection" in str(e).lower() or "websocket" in str(e).lower():
                self._is_connected = False
                self._record_failure(str(e))
                self._connection_errors.append({
                    "time": datetime.now().isoformat(),
                    "error": str(e),
                    "type": "query_error",
                })
            else:
                self._record_failure(str(e))
            yield ChatMessage(
                type=MessageType.ERROR,
                content=f"Error: {str(e)}"
            )
    
    def _parse_tool_call(self, msg: ToolCallMessage) -> ChatMessage:
        """
        解析工具调用消息
        
        Args:
            msg: ToolCallMessage 消息
        
        Returns:
            ChatMessage: 解析后的消息
        """
        status_map = {
            ToolCallStatus.PENDING: "pending",
            ToolCallStatus.IN_PROGRESS: "in_progress",
            ToolCallStatus.RUNNING: "in_progress",  # RUNNING 是 IN_PROGRESS 的别名
            ToolCallStatus.COMPLETED: "completed",
            ToolCallStatus.FAILED: "failed",
        }
        
        # 获取工具参数（SDK 使用 args 字段）
        tool_args = getattr(msg, 'args', None) or {}
        
        # 获取结果（从 content.markdown 字段提取）
        tool_result = None
        tool_error = None
        if hasattr(msg, 'content') and msg.content:
            content = msg.content
            # ToolCallContent 有 markdown 字段存储结果
            if hasattr(content, 'markdown') and content.markdown:
                tool_result = content.markdown
            # 检查是否有其他类型的错误信息
            if hasattr(content, 'error'):
                tool_error = content.error
        
        # 获取工具名称和 ID
        tool_name = msg.tool_name or msg.label or "unknown"
        tool_id = msg.id or f"{tool_name}-{hash(str(tool_args))}"
        
        # 日志记录，便于调试
        logger.debug(f"ToolCall: id={tool_id}, name={tool_name}, status={msg.status}, args={list(tool_args.keys()) if tool_args else []}, result_len={len(tool_result) if tool_result else 0}")
        
        return ChatMessage(
            type=MessageType.TOOL_CALL,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_arguments=tool_args,
            tool_status=status_map.get(msg.status, "in_progress"),
            tool_result=tool_result,
            tool_error=tool_error,
        )
    
    def _parse_tool_result(self, msg: ToolResultMessage) -> ChatMessage:
        """
        解析工具结果消息
        
        Args:
            msg: ToolResultMessage 消息
        
        Returns:
            ChatMessage: 解析后的消息
        """
        status_map = {
            ToolCallStatus.PENDING: "pending",
            ToolCallStatus.IN_PROGRESS: "in_progress",
            ToolCallStatus.RUNNING: "in_progress",
            ToolCallStatus.COMPLETED: "completed",
            ToolCallStatus.FAILED: "failed",
        }
        
        # ToolResultMessage 中 args 和 content 都有值
        tool_args = getattr(msg, 'args', None) or {}
        
        # 获取结果（从 content.markdown 字段提取）
        tool_result = None
        tool_error = None
        if hasattr(msg, 'content') and msg.content:
            content = msg.content
            if hasattr(content, 'markdown') and content.markdown:
                tool_result = content.markdown
            if hasattr(content, 'error'):
                tool_error = content.error
        
        # 获取工具名称和 ID
        tool_name = msg.tool_name or "unknown"
        tool_id = msg.id
        
        # 日志记录
        logger.debug(f"ToolResult: id={tool_id}, name={tool_name}, status={msg.status}, args_keys={list(tool_args.keys()) if tool_args else []}, result_len={len(tool_result) if tool_result else 0}")
        
        return ChatMessage(
            type=MessageType.TOOL_CALL,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_arguments=tool_args,
            tool_status=status_map.get(msg.status, "in_progress"),
            tool_result=tool_result,
            tool_error=tool_error,
        )
    
    async def query(self, message: str) -> str:
        """
        同步查询（返回完整响应）
        
        Args:
            message: 用户消息
        
        Returns:
            str: 完整响应文本
        """
        full_response = []
        
        async for msg in self.query_stream(message):
            if msg.type == MessageType.TEXT and msg.content:
                full_response.append(msg.content)
            elif msg.type == MessageType.ERROR:
                raise Exception(msg.content)
        
        return "".join(full_response)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()


# 全局客户端实例（可选，用于单例模式）
_global_client: Optional[IFlowClientService] = None


async def get_iflow_client() -> IFlowClientService:
    """
    获取全局 iFlow 客户端实例
    
    Returns:
        IFlowClientService: 客户端实例
    """
    global _global_client
    if _global_client is None:
        _global_client = IFlowClientService()
    return _global_client


async def close_iflow_client() -> None:
    """
    关闭全局 iFlow 客户端
    """
    global _global_client
    if _global_client:
        await _global_client.disconnect()
        _global_client = None


def extract_task_intent(response_text: str) -> Optional[Dict[str, Any]]:
    """
    从 AI 响应中提取定时任务意图
    
    Args:
        response_text: AI 响应文本
    
    Returns:
        Optional[Dict]: 如果检测到定时任务意图，返回 {"action": "create_task", "description": "..."}，否则返回 None
    """
    if not response_text:
        return None
    
    # 尝试提取 ```json ... ``` 块中的内容
    json_pattern = r'```json\s*([\s\S]*?)\s*```'
    matches = re.findall(json_pattern, response_text)
    
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, dict) and data.get("action") == "create_task":
                description = data.get("description", "")
                if description:
                    logger.info(f"Extracted task intent: {description}")
                    return data
        except json.JSONDecodeError:
            continue
    
    # 尝试提取 { ... } 块
    brace_pattern = r'\{[^{}]*"action"\s*:\s*"create_task"[^{}]*\}'
    matches = re.findall(brace_pattern, response_text)
    
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, dict) and data.get("action") == "create_task":
                description = data.get("description", "")
                if description:
                    logger.info(f"Extracted task intent: {description}")
                    return data
        except json.JSONDecodeError:
            continue
    
    return None


def remove_task_json_from_response(response_text: str) -> str:
    """
    从 AI 响应中移除定时任务 JSON 块，返回清理后的文本
    
    Args:
        response_text: AI 响应文本
    
    Returns:
        str: 清理后的文本
    """
    if not response_text:
        return response_text
    
    # 1. 移除 ```json ... ``` 块（包含 create_task 的）
    json_block_pattern = r'```json\s*\{[\s\S]*?"action"\s*:\s*"create_task"[\s\S]*?\}\s*```'
    cleaned = re.sub(json_block_pattern, '', response_text)
    
    # 2. 移除 ``` ... ``` 块（普通代码块中的 JSON）
    code_block_pattern = r'```\s*\{[\s\S]*?"action"\s*:\s*"create_task"[\s\S]*?\}\s*```'
    cleaned = re.sub(code_block_pattern, '', cleaned)
    
    # 3. 移除独立的 { ... } 块（单行或多行）
    # 处理多行 JSON
    multiline_json_pattern = r'\{[\s\S]*?"action"\s*:\s*"create_task"[\s\S]*?\}'
    cleaned = re.sub(multiline_json_pattern, '', cleaned)
    
    # 4. 移除纯 JSON 字符串（可能被转义）
    escaped_json_pattern = r'"\{[^"]*\\"action\\"\s*:\s*\\"create_task\\"[^"]*\}"'
    cleaned = re.sub(escaped_json_pattern, '', cleaned)
    
    # 5. 清理多余的空行和空格
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r'^\s+$', '', cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    
    return cleaned
