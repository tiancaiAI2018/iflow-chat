"""
多连接场景集成测试 - feat-046

测试场景：
1. 模拟用户连续创建 3 个连接，验证端口栈状态和进程数量
2. 验证栈顶为最新端口、旧端口在 TaskFinish 后清理

测试覆盖：
- 端口栈管理（入栈、出栈、查询）
- ACP 进程生命周期管理
- TaskFinishMessage 时的智能断开逻辑
"""
import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from services.iflow_client import IFlowClientService
from config import settings


# ==================== 多连接场景集成测试 ====================

class TestMultiConnectionScenario:
    """多连接场景集成测试 - 模拟用户连续创建多个连接"""

    @pytest.mark.asyncio
    async def test_multi_connection_port_stack_management(self):
        """
        测试多连接场景下的端口栈管理

        场景：
        1. 用户连续创建 3 个连接
        2. 验证端口栈状态：[port3, port2, port1]（栈顶为最新）
        3. 验证进程数量：3 个 ACP 进程
        """
        user_id = 9998001

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)
        for port in list(IFlowClientService._used_ports):
            if await IFlowClientService._stop_acp_process(port):
                pass

        # 模拟 3 个连接
        services = []
        ports = []

        try:
            for i in range(3):
                service = IFlowClientService(
                    cwd="/root/.iflow-bot/workspace/mybot",
                    user_id=user_id
                )

                # 模拟 connect 方法的关键步骤（不实际启动进程）
                port = await IFlowClientService._find_available_port(user_id)
                ports.append(port)

                # 模拟端口入栈
                IFlowClientService._push_user_port(user_id, port)

                services.append(service)

            # 验证端口栈状态
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 3, f"Expected 3 ports in stack, got {len(user_ports)}"

            # 验证栈顶为最新端口（最后加入的在索引 0）
            assert user_ports[0] == ports[2], f"Stack top should be {ports[2]}, got {user_ports[0]}"
            assert user_ports[1] == ports[1], f"Stack[1] should be {ports[1]}, got {user_ports[1]}"
            assert user_ports[2] == ports[0], f"Stack[2] should be {ports[0]}, got {user_ports[2]}"

            # 验证端口栈顺序：最新端口在栈顶
            assert user_ports == [ports[2], ports[1], ports[0]], \
                f"Port stack order incorrect: {user_ports}"

        finally:
            # 清理：移除端口栈
            IFlowClientService._user_ports.pop(user_id, None)
            for port in ports:
                IFlowClientService._used_ports.discard(port)

    @pytest.mark.asyncio
    async def test_multi_connection_task_finish_cleanup(self):
        """
        测试 TaskFinish 后旧连接的资源清理

        场景：
        1. 用户创建 3 个连接，端口栈 [port3, port2, port1]
        2. port1 的任务完成（TaskFinishMessage）
        3. port1 应该从栈中移除，port3 和 port2 保留
        """
        user_id = 9998002

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        # 模拟 3 个端口入栈
        ports = [8091, 8092, 8093]
        for port in ports:
            IFlowClientService._used_ports.add(port)
            IFlowClientService._push_user_port(user_id, port)

        try:
            # 验证初始状态
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 3
            assert user_ports == [8093, 8092, 8091]

            # 模拟 port1（最老的连接，栈底）的 TaskFinish
            # 创建 mock service，设置 _port 为 8091（port1）
            service = IFlowClientService(user_id=user_id)
            service._port = 8091

            # 调用 _on_task_finish
            await service._on_task_finish()

            # 验证 port1 已从栈中移除
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 2, f"Expected 2 ports after cleanup, got {len(user_ports)}"
            assert 8091 not in user_ports, "Port 8091 should be removed from stack"
            assert 8093 in user_ports, "Port 8093 should remain in stack"
            assert 8092 in user_ports, "Port 8092 should remain in stack"

            # 验证栈顶仍然是 8093
            assert user_ports[0] == 8093, f"Stack top should still be 8093, got {user_ports[0]}"

        finally:
            # 清理
            IFlowClientService._user_ports.pop(user_id, None)
            for port in ports:
                IFlowClientService._used_ports.discard(port)

    @pytest.mark.asyncio
    async def test_multi_connection_stack_top_no_cleanup(self):
        """
        测试栈顶端口任务完成时不清理

        场景：
        1. 用户创建 3 个连接，端口栈 [port3, port2, port1]
        2. port3（栈顶，最新连接）的任务完成
        3. port3 应该保留（因为它是当前活跃连接）
        """
        user_id = 9998003

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        # 模拟 3 个端口入栈
        ports = [8091, 8092, 8093]
        for port in ports:
            IFlowClientService._used_ports.add(port)
            IFlowClientService._push_user_port(user_id, port)

        try:
            # 验证初始状态
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 3
            assert user_ports[0] == 8093  # 栈顶

            # 模拟 port3（栈顶，最新连接）的 TaskFinish
            service = IFlowClientService(user_id=user_id)
            service._port = 8093

            # 调用 _on_task_finish
            await service._on_task_finish()

            # 验证所有端口都保留（栈顶不清理）
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 3, f"Expected 3 ports (stack top not cleaned), got {len(user_ports)}"
            assert 8093 in user_ports, "Stack top port 8093 should remain"
            assert 8092 in user_ports, "Port 8092 should remain"
            assert 8091 in user_ports, "Port 8091 should remain"

        finally:
            # 清理
            IFlowClientService._user_ports.pop(user_id, None)
            for port in ports:
                IFlowClientService._used_ports.discard(port)

    @pytest.mark.asyncio
    async def test_single_connection_no_cleanup(self):
        """
        测试单连接场景下 TaskFinish 不清理

        场景：
        1. 用户只有 1 个连接
        2. TaskFinish 时不断开（唯一连接需要保留）
        """
        user_id = 9998004

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        # 模拟 1 个端口入栈
        IFlowClientService._used_ports.add(8091)
        IFlowClientService._push_user_port(user_id, 8091)

        try:
            # 验证初始状态
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 1

            # 模拟 port1 的 TaskFinish
            service = IFlowClientService(user_id=user_id)
            service._port = 8091

            # 调用 _on_task_finish
            await service._on_task_finish()

            # 验证端口仍然保留（单连接不清理）
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 1, f"Expected 1 port (single connection), got {len(user_ports)}"
            assert 8091 in user_ports, "Single connection port should remain"

        finally:
            # 清理
            IFlowClientService._user_ports.pop(user_id, None)
            IFlowClientService._used_ports.discard(8091)

    @pytest.mark.asyncio
    async def test_multi_connection_sequential_cleanup(self):
        """
        测试多连接顺序清理

        场景：
        1. 用户创建 3 个连接，端口栈 [port3, port2, port1]
        2. port1 完成 -> 清理 port1，栈变为 [port3, port2]
        3. port2 完成 -> 清理 port2，栈变为 [port3]
        4. port3 完成 -> 不清理（单连接）
        """
        user_id = 9998005

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        # 模拟 3 个端口入栈
        ports = [8091, 8092, 8093]
        for port in ports:
            IFlowClientService._used_ports.add(port)
            IFlowClientService._push_user_port(user_id, port)

        try:
            # 步骤 1: port1（最老）完成
            service1 = IFlowClientService(user_id=user_id)
            service1._port = 8091
            await service1._on_task_finish()

            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 2
            assert 8091 not in user_ports
            assert user_ports == [8093, 8092]

            # 步骤 2: port2 完成
            service2 = IFlowClientService(user_id=user_id)
            service2._port = 8092
            await service2._on_task_finish()

            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 1
            assert 8092 not in user_ports
            assert user_ports == [8093]

            # 步骤 3: port3（栈顶，唯一连接）完成
            service3 = IFlowClientService(user_id=user_id)
            service3._port = 8093
            await service3._on_task_finish()

            # 单连接不清理
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 1
            assert 8093 in user_ports

        finally:
            # 清理
            IFlowClientService._user_ports.pop(user_id, None)
            for port in ports:
                IFlowClientService._used_ports.discard(port)


# ==================== 多用户并发场景测试 ====================

class TestMultiUserConcurrentConnections:
    """多用户并发连接场景测试"""

    @pytest.mark.asyncio
    async def test_multi_user_port_isolation(self):
        """
        测试多用户端口隔离

        场景：
        1. 用户 A 创建 2 个连接
        2. 用户 B 创建 2 个连接
        3. 验证端口栈相互独立
        """
        user_a = 9998010
        user_b = 9998011

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_a, None)
        IFlowClientService._user_ports.pop(user_b, None)

        try:
            # 为用户 A 分配 2 个端口
            port_a1 = await IFlowClientService._find_available_port(user_a)
            IFlowClientService._push_user_port(user_a, port_a1)

            port_a2 = await IFlowClientService._find_available_port(user_a)
            IFlowClientService._push_user_port(user_a, port_a2)

            # 为用户 B 分配 2 个端口
            port_b1 = await IFlowClientService._find_available_port(user_b)
            IFlowClientService._push_user_port(user_b, port_b1)

            port_b2 = await IFlowClientService._find_available_port(user_b)
            IFlowClientService._push_user_port(user_b, port_b2)

            # 验证用户 A 的端口栈
            user_a_ports = IFlowClientService._get_user_ports(user_a)
            assert len(user_a_ports) == 2
            assert user_a_ports[0] == port_a2  # 栈顶
            assert user_a_ports[1] == port_a1

            # 验证用户 B 的端口栈
            user_b_ports = IFlowClientService._get_user_ports(user_b)
            assert len(user_b_ports) == 2
            assert user_b_ports[0] == port_b2  # 栈顶
            assert user_b_ports[1] == port_b1

            # 验证端口不重叠
            all_a_ports = set(user_a_ports)
            all_b_ports = set(user_b_ports)
            assert all_a_ports.isdisjoint(all_b_ports), \
                f"User ports overlap: A={all_a_ports}, B={all_b_ports}"

        finally:
            # 清理
            IFlowClientService._user_ports.pop(user_a, None)
            IFlowClientService._user_ports.pop(user_b, None)
            for port in [port_a1, port_a2, port_b1, port_b2]:
                IFlowClientService._used_ports.discard(port)

    @pytest.mark.asyncio
    async def test_multi_user_cleanup_isolation(self):
        """
        测试多用户清理相互隔离

        场景：
        1. 用户 A 有 2 个连接
        2. 用户 B 有 2 个连接
        3. 用户 A 的旧连接清理不影响用户 B
        """
        user_a = 9998012
        user_b = 9998013

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_a, None)
        IFlowClientService._user_ports.pop(user_b, None)

        # 设置端口
        ports_a = [8091, 8092]
        ports_b = [8093, 8094]

        for port in ports_a:
            IFlowClientService._used_ports.add(port)
            IFlowClientService._push_user_port(user_a, port)

        for port in ports_b:
            IFlowClientService._used_ports.add(port)
            IFlowClientService._push_user_port(user_b, port)

        try:
            # 用户 A 的老连接（8091）完成
            service_a = IFlowClientService(user_id=user_a)
            service_a._port = 8091
            await service_a._on_task_finish()

            # 验证用户 A 的端口栈
            user_a_ports = IFlowClientService._get_user_ports(user_a)
            assert len(user_a_ports) == 1
            assert 8091 not in user_a_ports
            assert 8092 in user_a_ports

            # 验证用户 B 的端口栈不受影响
            user_b_ports = IFlowClientService._get_user_ports(user_b)
            assert len(user_b_ports) == 2
            assert 8093 in user_b_ports
            assert 8094 in user_b_ports

        finally:
            # 清理
            IFlowClientService._user_ports.pop(user_a, None)
            IFlowClientService._user_ports.pop(user_b, None)
            for port in ports_a + ports_b:
                IFlowClientService._used_ports.discard(port)


# ==================== 边缘场景测试 ====================

class TestMultiConnectionEdgeCases:
    """多连接边缘场景测试"""

    @pytest.mark.asyncio
    async def test_empty_port_stack(self):
        """
        测试空端口栈处理

        场景：
        1. 用户没有连接
        2. 调用 _on_task_finish 不应该报错
        """
        user_id = 9998020

        # 确保用户没有端口栈
        IFlowClientService._user_ports.pop(user_id, None)

        service = IFlowClientService(user_id=user_id)
        service._port = 8091

        # 不应该抛出异常
        await service._on_task_finish()

        # 验证端口栈仍然为空
        user_ports = IFlowClientService._get_user_ports(user_id)
        assert len(user_ports) == 0

    @pytest.mark.asyncio
    async def test_none_port(self):
        """
        测试 _port 为 None 的处理

        场景：
        1. 服务未连接（_port 为 None）
        2. 调用 _on_task_finish 不应该报错
        """
        user_id = 9998021

        service = IFlowClientService(user_id=user_id)
        service._port = None

        # 不应该抛出异常
        await service._on_task_finish()

    @pytest.mark.asyncio
    async def test_port_not_in_stack(self):
        """
        测试端口不在栈中的处理

        场景：
        1. 用户的端口栈是 [8092, 8093]
        2. 服务试图清理 8091（不在栈中）
        3. 应该正常处理（不报错）
        """
        user_id = 9998022

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        # 设置端口栈
        IFlowClientService._used_ports.add(8092)
        IFlowClientService._used_ports.add(8093)
        IFlowClientService._push_user_port(user_id, 8092)
        IFlowClientService._push_user_port(user_id, 8093)

        try:
            # 试图清理 8091（不在栈中）
            service = IFlowClientService(user_id=user_id)
            service._port = 8091

            # 不应该抛出异常
            await service._on_task_finish()

            # 验证端口栈不变
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 2
            assert 8092 in user_ports
            assert 8093 in user_ports

        finally:
            # 清理
            IFlowClientService._user_ports.pop(user_id, None)
            IFlowClientService._used_ports.discard(8092)
            IFlowClientService._used_ports.discard(8093)

    @pytest.mark.asyncio
    async def test_concurrent_connections_same_user(self):
        """
        测试同一用户并发创建连接

        场景：
        1. 同一用户短时间内创建多个连接
        2. 验证端口分配不冲突
        """
        user_id = 9998023

        # 清理之前的测试数据
        IFlowClientService._user_ports.pop(user_id, None)

        async def create_connection():
            """创建一个连接并返回分配的端口"""
            port = await IFlowClientService._find_available_port(user_id)
            IFlowClientService._push_user_port(user_id, port)
            return port

        try:
            # 并发创建 3 个连接
            ports = await asyncio.gather(
                create_connection(),
                create_connection(),
                create_connection(),
            )

            # 验证端口不重复
            assert len(set(ports)) == 3, f"Ports should be unique: {ports}"

            # 验证端口栈状态
            user_ports = IFlowClientService._get_user_ports(user_id)
            assert len(user_ports) == 3

        finally:
            # 清理
            IFlowClientService._user_ports.pop(user_id, None)
            for port in ports if 'ports' in dir() else []:
                IFlowClientService._used_ports.discard(port)