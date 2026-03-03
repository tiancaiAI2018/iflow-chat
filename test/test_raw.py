#!/usr/bin/env python3
"""测试 iflow-sdk RawDataClient - 查看原始协议数据"""
import asyncio

async def test_raw_client():
    print("=" * 50)
    print("测试: RawDataClient 原始协议数据")
    print("=" * 50)
    
    from iflow_sdk import RawDataClient, IFlowOptions
    
    options = IFlowOptions(url="ws://localhost:8090/acp", auto_start_process=False, timeout=30.0)
    client = RawDataClient(options=options)
    
    try:
        print("\n1. 连接到服务器...")
        await client.connect()
        print("✓ 已连接")
        
        # 发送消息
        print("\n2. 发送测试消息: '你好'")
        await client.send_message("你好")
        print("✓ 消息已发送")
        
        # 接收原始消息
        print("\n3. 接收响应...")
        msg_count = 0
        async with asyncio.timeout(20):
            async for raw_msg in client.receive_raw_messages():
                msg_count += 1
                print(f"\n--- 原始消息 {msg_count} ---")
                print(f"message_type: {raw_msg.message_type}")
                print(f"is_control: {raw_msg.is_control}")
                
                # json_data 可能是 dict 或 str
                data = raw_msg.json_data
                if isinstance(data, dict):
                    import json
                    print(f"数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
                elif isinstance(data, str):
                    print(f"原始数据: {data}")
                else:
                    print(f"数据类型: {type(data)}, 值: {data}")
                
                # 检查是否是结束消息
                if raw_msg.message_type == "task/finish":
                    print("\n✓ 任务完成")
                    break
                    
                if msg_count >= 100:
                    print("\n达到消息上限")
                    break
        
        print(f"\n共收到 {msg_count} 条消息")
        
    except asyncio.TimeoutError:
        print("✗ 超时")
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()
        print("\n连接已关闭")

if __name__ == "__main__":
    asyncio.run(test_raw_client())