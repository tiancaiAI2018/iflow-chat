"""
数据库迁移：添加 push_key 字段到 users 表

运行方式：
    PYTHONPATH=/root/.iflow-bot/workspace/mybot python backend/migrations/add_push_key_field.py
"""
import asyncio
import logging
from sqlalchemy import text
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    """执行迁移：添加 push_key 字段"""
    async with engine.begin() as conn:
        # 检查字段是否已存在
        result = await conn.execute(
            text("PRAGMA table_info(users)")
        )
        columns = [row[1] for row in result.fetchall()]
        
        if 'push_key' in columns:
            logger.info("push_key 字段已存在，跳过迁移")
            return
        
        # 添加 push_key 字段
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN push_key VARCHAR(100)")
        )
        logger.info("成功添加 push_key 字段到 users 表")


if __name__ == "__main__":
    asyncio.run(migrate())
