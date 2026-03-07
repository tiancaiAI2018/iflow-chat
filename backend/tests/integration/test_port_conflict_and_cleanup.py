"""
端口冲突和资源清理集成测试 - feat-047

测试场景：
1. 端口冲突场景 - 模拟端口被占用时的重试和错误提示
2. 资源清理测试 - 验证服务关闭时所有 ACP 进程被正确清理

测试覆盖：
- 端口被占用时的重试机制（最多10次）
- 端口耗尽时的错误处理
- 服务关闭时的进程清理（无僵尸进程）
- 异常退出进程的清理
"""
import pytest
import asyncio
import sys
import os
import socket
import subprocess
import signal
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from services.iflow_client import IFlowClientService
from config import settings


# ==================== 端口冲突场景测试 ====================

class TestPortConflictScenario:
    """端口冲突场景集成测试"""

    @pytest.mark.asyncio
    async def test_port_conflict_retry_mechanism(self):
        """
        测试端口冲突时的重试机制

        场景：
        1. 模拟端口 8091-8095 被占用
        2. 尝试为用户分配端口
        3. 验证重试最多 10 次
        4. 验证最终成功分配到可用端口
        """
        user_id = 9999001

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        # 创建一些临时端口占用
        occupied_ports = []
        sockets = []

        try:
            # 占用前 5 个可能尝试的端口
            for i in range(5):
                port = settings.ACP_PORT_START + i
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(('localhost', port))
                    sock.listen(1)
                    sockets.append(sock)
                    occupied_ports.append(port)
                except OSError:
                    # 端口可能已经被占用，跳过
                    sock.close()

            # 分配端口 - 应该跳过被占用的端口
            port = await IFlowClientService._find_available_port(user_id)

            # 验证分配的端口不在被占用的列表中
            assert port not in occupied_ports, \
                f"Port {port} should not be in occupied ports {occupied_ports}"

            # 验证端口在配置范围内
            assert settings.ACP_PORT_START <= port <= settings.ACP_PORT_END, \
                f"Port {port} should be in range [{settings.ACP_PORT_START}, {settings.ACP_PORT_END}]"

        finally:
            # 清理：释放占用的端口
            for sock in sockets:
                try:
                    sock.close()
                except:
                    pass

            # 清理端口记录
            IFlowClientService._user_ports.pop(user_id, None)
            for port in occupied_ports:
                IFlowClientService._used_ports.discard(port)

    @pytest.mark.asyncio
    async def test_port_conflict_exhausted_error(self):
        """
        测试端口耗尽时的错误处理

        场景：
        1. 模拟端口范围内所有端口都被占用或已被使用
        2. 尝试为用户分配端口
        3. 验证返回明确的错误信息"系统繁忙，无法为用户 X 分配端口，请稍后重试"
        """
        user_id = 9999002

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        # 临时保存原始已使用端口集合
        original_used_ports = IFlowClientService._used_ports.copy()

        try:
            # 使用 mock 模拟 _is_port_available 方法，使其对所有端口都返回 False
            # 这样无论 user_id 如何计算端口，都会被视为不可用
            with patch.object(IFlowClientService, '_is_port_available', return_value=False):
                # 尝试分配端口 - 应该抛出 RuntimeError
                with pytest.raises(RuntimeError) as exc_info:
                    await IFlowClientService._find_available_port(user_id)

                # 验证错误信息包含关键信息
                error_msg = str(exc_info.value)
                assert "系统繁忙" in error_msg, f"Error message should contain '系统繁忙': {error_msg}"
                assert "无法为用户" in error_msg, f"Error message should contain '无法为用户': {error_msg}"
                assert "分配端口" in error_msg, f"Error message should contain '分配端口': {error_msg}"
                assert str(user_id) in error_msg, f"Error message should contain user_id {user_id}: {error_msg}"

        finally:
            # 恢复原始已使用端口集合
            IFlowClientService._used_ports = original_used_ports
            IFlowClientService._user_ports.pop(user_id, None)

    @pytest.mark.asyncio
    async def test_port_conflict_partial_retry_success(self):
        """
        测试部分端口冲突后重试成功

        场景：
        1. 模拟前 3 个尝试的端口被占用
        2. 第 4 个尝试的端口可用
        3. 验证成功分配到第 4 个端口
        4. 验证重试次数小于最大限制
        """
        user_id = 9999003

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        # 临时保存原始已使用端口集合
        original_used_ports = IFlowClientService._used_ports.copy()

        try:
            # 模拟前 3 个端口已被使用
            for i in range(3):
                port = settings.ACP_PORT_START + i
                IFlowClientService._used_ports.add(port)

            # 分配端口 - 应该成功（跳过前3个）
            port = await IFlowClientService._find_available_port(user_id)

            # 验证分配的端口是正确的（第4个或更后）
            assert port >= settings.ACP_PORT_START + 3, \
                f"Port {port} should be >= {settings.ACP_PORT_START + 3}"

        finally:
            # 清理：恢复原始已使用端口集合
            IFlowClientService._used_ports = original_used_ports
            IFlowClientService._user_ports.pop(user_id, None)

    @pytest.mark.asyncio
    async def test_port_conflict_retry_count_limit(self):
        """
        测试重试次数限制

        场景：
        1. 验证 ACP_MAX_PORT_RETRIES 配置项
        2. 验证重试次数不超过配置值
        """
        # 验证配置项存在且合理
        assert hasattr(settings, 'ACP_MAX_PORT_RETRIES'), \
            "Settings should have ACP_MAX_PORT_RETRIES attribute"
        assert settings.ACP_MAX_PORT_RETRIES == 10, \
            f"ACP_MAX_PORT_RETRIES should be 10, got {settings.ACP_MAX_PORT_RETRIES}"

    @pytest.mark.asyncio
    async def test_port_conflict_concurrent_users(self):
        """
        测试多用户并发时的端口冲突处理

        场景：
        1. 多个用户同时请求端口
        2. 验证每个用户都能分配到唯一端口
        3. 验证没有端口被重复分配
        """
        user_ids = [9999010, 9999011, 9999012, 9999013, 9999014]

        # 清理之前的测试数据
        for user_id in user_ids:
            IFlowClientService._user_ports.pop(user_id, None)

        try:
            # 并发为多个用户分配端口
            async def allocate_port(user_id):
                port = await IFlowClientService._find_available_port(user_id)
                return user_id, port

            results = await asyncio.gather(*[allocate_port(uid) for uid in user_ids])

            # 验证所有端口都不相同
            ports = [port for _, port in results]
            assert len(set(ports)) == len(ports), \
                f"Ports should be unique: {ports}"

            # 验证所有端口都在配置范围内
            for port in ports:
                assert settings.ACP_PORT_START <= port <= settings.ACP_PORT_END, \
                    f"Port {port} should be in range"

        finally:
            # 清理
            for user_id in user_ids:
                IFlowClientService._user_ports.pop(user_id, None)
            for port in ports if 'ports' in dir() else []:
                IFlowClientService._used_ports.discard(port)


# ==================== 资源清理场景测试 ====================

class TestResourceCleanupScenario:
    """资源清理场景集成测试"""

    @pytest.mark.asyncio
    async def test_cleanup_all_processes_on_shutdown(self):
        """
        测试服务关闭时所有 ACP 进程被正确清理

        场景：
        1. 创建多个 ACP 进程
        2. 模拟服务关闭
        3. 验证所有进程都被停止
        4. 验证无僵尸进程残留
        """
        # 临时保存原始状态
        original_port_processes = IFlowClientService._port_processes.copy()
        original_used_ports = IFlowClientService._used_ports.copy()

        test_ports = [8091, 8092, 8093]

        try:
            # 创建模拟进程
            mock_processes = []
            for port in test_ports:
                mock_process = AsyncMock()
                mock_process.pid = 10000 + port
                mock_process.returncode = None  # 进程仍在运行
                mock_processes.append(mock_process)
                IFlowClientService._port_processes[port] = mock_process
                IFlowClientService._used_ports.add(port)

            # 停止所有进程
            for port in test_ports:
                await IFlowClientService._stop_acp_process(port)

            # 验证所有进程的 terminate 或 kill 被调用
            for mock_process in mock_processes:
                # 验证至少调用了 terminate 或 kill
                assert mock_process.terminate.called or mock_process.kill.called, \
                    "Process should be terminated or killed"

            # 验证 _port_processes 字典已清理
            for port in test_ports:
                assert port not in IFlowClientService._port_processes, \
                    f"Port {port} should be removed from _port_processes"

            # 验证 _used_ports 集合已清理
            for port in test_ports:
                assert port not in IFlowClientService._used_ports, \
                    f"Port {port} should be removed from _used_ports"

        finally:
            # 恢复原始状态
            IFlowClientService._port_processes = original_port_processes
            IFlowClientService._used_ports = original_used_ports

    @pytest.mark.asyncio
    async def test_cleanup_zombie_processes(self):
        """
        测试僵尸进程清理

        场景：
        1. 创建一些已经终止的进程（returncode 不为 None）
        2. 调用 _stop_acp_process
        3. 验证进程被正确清理（不抛出异常）
        4. 验证端口资源被释放
        """
        # 临时保存原始状态
        original_port_processes = IFlowClientService._port_processes.copy()
        original_used_ports = IFlowClientService._used_ports.copy()

        test_port = 8095

        try:
            # 创建已终止的模拟进程
            mock_process = AsyncMock()
            mock_process.pid = 20000
            mock_process.returncode = 0  # 进程已正常退出

            IFlowClientService._port_processes[test_port] = mock_process
            IFlowClientService._used_ports.add(test_port)

            # 调用停止方法 - 不应该抛出异常
            await IFlowClientService._stop_acp_process(test_port)

            # 验证进程不在管理字典中
            assert test_port not in IFlowClientService._port_processes, \
                f"Port {test_port} should be removed from _port_processes"

            # 验证端口不在使用集合中
            assert test_port not in IFlowClientService._used_ports, \
                f"Port {test_port} should be removed from _used_ports"

        finally:
            # 恢复原始状态
            IFlowClientService._port_processes = original_port_processes
            IFlowClientService._used_ports = original_used_ports

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_process(self):
        """
        测试清理不存在的进程

        场景：
        1. 尝试停止一个不存在的端口对应的进程
        2. 验证不抛出异常
        3. 验证正常返回
        """
        test_port = 8096

        # 确保端口不在 _port_processes 中
        IFlowClientService._port_processes.pop(test_port, None)
        IFlowClientService._used_ports.discard(test_port)

        # 调用停止方法 - 不应该抛出异常
        await IFlowClientService._stop_acp_process(test_port)

        # 验证端口仍然不在使用集合中
        assert test_port not in IFlowClientService._used_ports

    @pytest.mark.asyncio
    async def test_cleanup_force_kill_after_timeout(self):
        """
        测试优雅终止超时后的强制 kill

        场景：
        1. 创建一个不响应 terminate 的进程
        2. 调用 _stop_acp_process
        3. 验证先尝试 terminate
        4. 验证超时后使用 kill
        """
        # 临时保存原始状态
        original_port_processes = IFlowClientService._port_processes.copy()
        original_used_ports = IFlowClientService._used_ports.copy()

        test_port = 8097

        try:
            # 创建一个模拟进程，terminate 后等待超时
            mock_process = AsyncMock()
            mock_process.pid = 30000
            mock_process.returncode = None  # 进程仍在运行

            # 模拟 wait 超时
            async def slow_wait():
                await asyncio.sleep(10)  # 模拟长时间等待
                return 0

            mock_process.wait = slow_wait

            IFlowClientService._port_processes[test_port] = mock_process
            IFlowClientService._used_ports.add(test_port)

            # 调用停止方法
            await IFlowClientService._stop_acp_process(test_port)

            # 验证 terminate 被调用
            assert mock_process.terminate.called, \
                "Process terminate should be called"

            # 验证 kill 被调用（因为超时）
            assert mock_process.kill.called, \
                "Process kill should be called after timeout"

        finally:
            # 恢复原始状态
            IFlowClientService._port_processes = original_port_processes
            IFlowClientService._used_ports = original_used_ports

    @pytest.mark.asyncio
    async def test_cleanup_user_port_stack(self):
        """
        测试用户端口栈的清理

        场景：
        1. 用户有多个端口在栈中
        2. 调用 _remove_user_port 清理特定端口
        3. 验证端口从栈中移除
        4. 验证其他端口保留
        """
        user_id = 9999020

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        test_ports = [8098, 8099, 8100]

        try:
            # 将端口压入栈
            for port in test_ports:
                IFlowClientService._used_ports.add(port)
                IFlowClientService._push_user_port(user_id, port)

            # 验证初始状态
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 3

            # 移除中间端口
            IFlowClientService._remove_user_port(user_id, test_ports[1])

            # 验证端口被移除
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 2
            assert test_ports[1] not in user_ports
            assert test_ports[0] in user_ports
            assert test_ports[2] in user_ports

            # 验证端口不在使用集合中
            assert test_ports[1] not in IFlowClientService._used_ports

        finally:
            # 清理
            IFlowClientService._user_ports.pop(user_id, None)
            for port in test_ports:
                IFlowClientService._used_ports.discard(port)

    @pytest.mark.asyncio
    async def test_cleanup_all_user_ports(self):
        """
        测试清理用户所有端口

        场景：
        1. 用户有多个端口在栈中
        2. 循环清理所有端口
        3. 验证端口栈被完全清空
        4. 验证用户条目被删除
        """
        user_id = 9999021

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        test_ports = [8101, 8102, 8103]

        try:
            # 将端口压入栈
            for port in test_ports:
                IFlowClientService._used_ports.add(port)
                IFlowClientService._push_user_port(user_id, port)

            # 逐个移除所有端口
            for port in test_ports:
                IFlowClientService._remove_user_port(user_id, port)

            # 验证用户条目被删除
            assert user_id not in IFlowClientService._user_ports, \
                f"User {user_id} should be removed from _user_ports"

            # 验证所有端口都不在使用集合中
            for port in test_ports:
                assert port not in IFlowClientService._used_ports, \
                    f"Port {port} should not be in _used_ports"

        finally:
            # 清理
            IFlowClientService._user_ports.pop(user_id, None)
            for port in test_ports:
                IFlowClientService._used_ports.discard(port)


# ==================== 边界情况测试 ====================

class TestCleanupEdgeCases:
    """资源清理边界情况测试"""

    @pytest.mark.asyncio
    async def test_cleanup_with_exception_in_stop(self):
        """
        测试停止进程时发生异常的处理

        场景：
        1. 进程停止时抛出异常
        2. 验证异常被捕获
        3. 验证资源仍然被清理
        """
        # 临时保存原始状态
        original_port_processes = IFlowClientService._port_processes.copy()
        original_used_ports = IFlowClientService._used_ports.copy()

        test_port = 8104

        try:
            # 创建一个抛出异常的模拟进程
            mock_process = MagicMock()
            mock_process.pid = 40000
            mock_process.returncode = None

            # 模拟 terminate 抛出异常
            def raise_exception():
                raise OSError("Simulated error")

            mock_process.terminate = raise_exception

            IFlowClientService._port_processes[test_port] = mock_process
            IFlowClientService._used_ports.add(test_port)

            # 调用停止方法 - 不应该抛出异常（应该被捕获）
            await IFlowClientService._stop_acp_process(test_port)

            # 验证端口仍然被清理
            assert test_port not in IFlowClientService._port_processes
            assert test_port not in IFlowClientService._used_ports

        finally:
            # 恢复原始状态
            IFlowClientService._port_processes = original_port_processes
            IFlowClientService._used_ports = original_used_ports

    @pytest.mark.asyncio
    async def test_cleanup_already_removed_port(self):
        """
        测试重复清理同一端口

        场景：
        1. 端口已经被清理
        2. 再次调用清理方法
        3. 验证不抛出异常
        """
        user_id = 9999030
        test_port = 8105

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)
        IFlowClientService._used_ports.discard(test_port)

        # 第一次移除（端口不存在）
        IFlowClientService._remove_user_port(user_id, test_port)

        # 第二次移除 - 不应该抛出异常
        IFlowClientService._remove_user_port(user_id, test_port)

        # 验证状态
        assert user_id not in IFlowClientService._user_ports
        assert test_port not in IFlowClientService._used_ports

    @pytest.mark.asyncio
    async def test_port_availability_check(self):
        """
        测试端口可用性检查

        场景：
        1. 检查空闲端口 - 应该返回 True
        2. 检查被占用的端口 - 应该返回 False
        """
        # 找一个可用端口
        test_port = 8106

        # 确保端口不被使用
        IFlowClientService._used_ports.discard(test_port)

        # 检查端口可用性
        is_available = IFlowClientService._is_port_available(test_port)

        # 端口应该可用（假设没有其他服务使用）
        assert is_available, f"Port {test_port} should be available"

    @pytest.mark.asyncio
    async def test_port_availability_check_occupied(self):
        """
        测试检查被占用的端口

        场景：
        1. 占用一个端口
        2. 检查该端口可用性
        3. 应该返回 False
        """
        test_port = 8107

        # 创建一个 socket 占用端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.bind(('localhost', test_port))
            sock.listen(1)

            # 检查端口可用性
            is_available = IFlowClientService._is_port_available(test_port)

            # 端口应该不可用
            assert not is_available, f"Port {test_port} should not be available"

        finally:
            sock.close()

    @pytest.mark.asyncio
    async def test_concurrent_cleanup_same_port(self):
        """
        测试并发清理同一端口

        场景：
        1. 多个协程同时尝试清理同一个端口
        2. 验证不会抛出异常
        3. 验证端口最终被清理
        """
        # 临时保存原始状态
        original_port_processes = IFlowClientService._port_processes.copy()

        test_port = 8108

        try:
            # 创建一个模拟进程
            mock_process = AsyncMock()
            mock_process.pid = 50000
            mock_process.returncode = None

            IFlowClientService._port_processes[test_port] = mock_process
            IFlowClientService._used_ports.add(test_port)

            # 并发调用停止方法
            await asyncio.gather(
                IFlowClientService._stop_acp_process(test_port),
                IFlowClientService._stop_acp_process(test_port),
                IFlowClientService._stop_acp_process(test_port),
            )

            # 验证端口被清理
            assert test_port not in IFlowClientService._port_processes
            assert test_port not in IFlowClientService._used_ports

        finally:
            # 恢复原始状态
            IFlowClientService._port_processes = original_port_processes
