#!/usr/bin/env python3
"""测试 iflow-sdk 基础连接"""
import asyncio
import sys

async def test_connection():
    print("=" * 50)
    print("测试 1: 基础连接测试")
    print("=" * 50)
    
    try:
        # 尝试导入 SDK
        from iflow_sdk import IFlowClient, IFlowOptions
        print("✓ SDK 导入成功")
    except ImportError as e:
        print(f"✗ SDK 导入失败: {e}")
        return
    
    # 连接到已有的 8090 端口服务
    options = IFlowOptions(
        url="ws://localhost:8090/acp",
        auto_start_process=False,  # 手动模式，不自动启动
        timeout=10.0  # 短超时便于调试
    )
    
    print(f"正在连接 ws://localhost:8090/acp ...")
    
    try:
        # 使用超时保护
        async with asyncio.timeout(15):
            async with IFlowClient(options) as client:
                print("✓ 成功连接到 ws://localhost:8090/acp")
                
                # 发送简单消息
                await client.send_message("你好")
                print("✓ 消息已发送，等待响应...")
                
                # 接收响应 - 只读取前几条消息
                count = 0
                async for message in client.receive_messages():
                    count += 1
                    print(f"\n[消息 {count}] 类型: {type(message).__name__}")
                    print(f"内容: {message}")
                    if count >= 10:  # 限制消息数量
                        print("\n已收到 10 条消息，停止接收")
                        break
                    
    except asyncio.TimeoutError:
        print("✗ 操作超时")
    except Exception as e:
        print(f"✗ 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
