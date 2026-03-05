#!/usr/bin/env python3
"""
数据库迁移脚本：为现有会话设置默认工作目录

功能：
1. 检查 conversations 表是否存在 working_directory 字段
2. 如果不存在，添加该字段并设置默认值
3. 更新所有 working_directory 为 NULL 的记录为默认值

创建时间：2026-03-05
功能ID：feat-010
"""

import sqlite3
import os
from pathlib import Path

# 默认工作目录
DEFAULT_WORKING_DIRECTORY = "/root/.iflow-bot/workspace"

# 数据库路径（相对于项目根目录）
# 脚本位于 backend/migrations/，需要回到项目根目录再进入 data/
DB_PATH = Path(__file__).parent.parent.parent / "data" / "app.db"


def get_db_connection():
    """获取数据库连接"""
    return sqlite3.connect(str(DB_PATH))


def check_column_exists(conn, table_name, column_name):
    """检查表中是否存在指定字段"""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def migrate_database():
    """执行数据库迁移"""
    print(f"开始数据库迁移...")
    print(f"数据库路径: {DB_PATH}")
    
    # 检查数据库文件是否存在
    if not DB_PATH.exists():
        print(f"错误：数据库文件不存在: {DB_PATH}")
        return False
    
    conn = get_db_connection()
    
    try:
        # 1. 检查 conversations 表是否存在
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
        )
        if not cursor.fetchone():
            print("警告：conversations 表不存在，跳过迁移")
            return True
        
        # 2. 检查 working_directory 字段是否存在
        if not check_column_exists(conn, "conversations", "working_directory"):
            print("working_directory 字段不存在，开始添加字段...")
            conn.execute(
                f"ALTER TABLE conversations ADD COLUMN working_directory VARCHAR(500) DEFAULT '{DEFAULT_WORKING_DIRECTORY}'"
            )
            conn.commit()
            print("字段添加成功")
        else:
            print("working_directory 字段已存在")
        
        # 3. 更新所有 NULL 值为默认值
        cursor = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE working_directory IS NULL"
        )
        null_count = cursor.fetchone()[0]
        
        if null_count > 0:
            print(f"发现 {null_count} 条记录的 working_directory 为 NULL，开始更新...")
            conn.execute(
                f"UPDATE conversations SET working_directory = '{DEFAULT_WORKING_DIRECTORY}' WHERE working_directory IS NULL"
            )
            conn.commit()
            print(f"成功更新 {null_count} 条记录")
        else:
            print("所有记录的 working_directory 已有值，无需更新")
        
        # 4. 验证迁移结果
        cursor = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE working_directory IS NULL"
        )
        remaining_nulls = cursor.fetchone()[0]
        
        if remaining_nulls == 0:
            print("迁移成功：所有会话都有有效的工作目录")
            return True
        else:
            print(f"迁移失败：仍有 {remaining_nulls} 条记录的 working_directory 为 NULL")
            return False
            
    except Exception as e:
        print(f"迁移失败：{e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = migrate_database()
    exit(0 if success else 1)
