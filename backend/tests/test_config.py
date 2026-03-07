"""
Redis 配置加载测试用例

测试目标：
- REDIS_URL 配置正确读取
- REDIS_MESSAGE_TTL 配置正确读取
- 配置默认值正确
"""
import sys
import os

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestRedisConfig:
    """测试 Redis 配置"""

    def test_redis_url_config_exists(self):
        """测试 REDIS_URL 配置存在"""
        from config import settings

        assert hasattr(settings, 'REDIS_URL'), "settings 应该有 REDIS_URL 配置"

    def test_redis_url_default_value(self):
        """测试 REDIS_URL 默认值"""
        from config import settings

        assert settings.REDIS_URL == "redis://localhost:6379/0"

    def test_redis_message_ttl_config_exists(self):
        """测试 REDIS_MESSAGE_TTL 配置存在"""
        from config import settings

        assert hasattr(settings, 'REDIS_MESSAGE_TTL'), "settings 应该有 REDIS_MESSAGE_TTL 配置"

    def test_redis_message_ttl_default_value(self):
        """测试 REDIS_MESSAGE_TTL 默认值（5分钟 = 300秒）"""
        from config import settings

        assert settings.REDIS_MESSAGE_TTL == 300

    def test_redis_max_memory_config_exists(self):
        """测试 REDIS_MAX_MEMORY 配置存在"""
        from config import settings

        assert hasattr(settings, 'REDIS_MAX_MEMORY'), "settings 应该有 REDIS_MAX_MEMORY 配置"

    def test_redis_max_memory_default_value(self):
        """测试 REDIS_MAX_MEMORY 默认值"""
        from config import settings

        assert settings.REDIS_MAX_MEMORY == "32mb"


class TestConfigIntegration:
    """测试配置与其他模块的集成"""

    def test_redis_url_can_be_used_for_connection(self):
        """测试 REDIS_URL 可以用于连接 Redis"""
        import redis.asyncio as aioredis
        from config import settings

        # 验证 URL 格式正确
        assert settings.REDIS_URL.startswith("redis://")

    def test_redis_message_ttl_is_integer(self):
        """测试 REDIS_MESSAGE_TTL 是整数类型"""
        from config import settings

        assert isinstance(settings.REDIS_MESSAGE_TTL, int)
        assert settings.REDIS_MESSAGE_TTL > 0


class TestACPConfig:
    """测试 ACP 进程配置"""

    def test_acp_port_start_config_exists(self):
        """测试 ACP_PORT_START 配置存在"""
        from config import settings

        assert hasattr(settings, 'ACP_PORT_START'), "settings 应该有 ACP_PORT_START 配置"

    def test_acp_port_start_default_value(self):
        """测试 ACP_PORT_START 默认值"""
        from config import settings

        assert settings.ACP_PORT_START == 8091

    def test_acp_port_start_is_integer(self):
        """测试 ACP_PORT_START 是整数类型"""
        from config import settings

        assert isinstance(settings.ACP_PORT_START, int)

    def test_acp_port_end_config_exists(self):
        """测试 ACP_PORT_END 配置存在"""
        from config import settings

        assert hasattr(settings, 'ACP_PORT_END'), "settings 应该有 ACP_PORT_END 配置"

    def test_acp_port_end_default_value(self):
        """测试 ACP_PORT_END 默认值"""
        from config import settings

        assert settings.ACP_PORT_END == 9000

    def test_acp_port_end_is_integer(self):
        """测试 ACP_PORT_END 是整数类型"""
        from config import settings

        assert isinstance(settings.ACP_PORT_END, int)

    def test_acp_max_port_retries_config_exists(self):
        """测试 ACP_MAX_PORT_RETRIES 配置存在"""
        from config import settings

        assert hasattr(settings, 'ACP_MAX_PORT_RETRIES'), "settings 应该有 ACP_MAX_PORT_RETRIES 配置"

    def test_acp_max_port_retries_default_value(self):
        """测试 ACP_MAX_PORT_RETRIES 默认值"""
        from config import settings

        assert settings.ACP_MAX_PORT_RETRIES == 10

    def test_acp_max_port_retries_is_integer(self):
        """测试 ACP_MAX_PORT_RETRIES 是整数类型"""
        from config import settings

        assert isinstance(settings.ACP_MAX_PORT_RETRIES, int)

    def test_acp_startup_timeout_config_exists(self):
        """测试 ACP_STARTUP_TIMEOUT 配置存在"""
        from config import settings

        assert hasattr(settings, 'ACP_STARTUP_TIMEOUT'), "settings 应该有 ACP_STARTUP_TIMEOUT 配置"

    def test_acp_startup_timeout_default_value(self):
        """测试 ACP_STARTUP_TIMEOUT 默认值"""
        from config import settings

        assert settings.ACP_STARTUP_TIMEOUT == 5.0

    def test_acp_startup_timeout_is_float(self):
        """测试 ACP_STARTUP_TIMEOUT 是浮点数类型"""
        from config import settings

        assert isinstance(settings.ACP_STARTUP_TIMEOUT, float)
