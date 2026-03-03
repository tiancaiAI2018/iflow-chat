#!/usr/bin/env python3
"""测试 iflow-sdk 多工具调用场景"""
import asyncio

async def test_multiple_tools():
    print("=" * 50)
    print("测试: 多工具调用场景")
    print("=" * 50)
    
    from iflow_sdk import (
        IFlowClient, IFlowOptions,
        AssistantMessage, ToolCallMessage, TaskFinishMessage,
        ToolCallStatus
    )
    
    options = IFlowOptions(
        url="ws://localhost:8090/acp",
        auto_start_process=False,
        timeout=120.0
    )
    
    try:
        async with IFlowClient(options) as client:
            print("✓ 已连接")
            
            # 发送一个需要多个工具的复杂请求
            prompt = """请执行以下任务：
1. 列出当前目录的文件
2. 读取 test_query.py 文件的内容（前10行）
"""
            await client.send_message(prompt)
            print("✓ 消息已发送\n")
            
            print("--- 响应流 ---\n")
            
            tool_calls_info = []
            current_tool = None
            
            async for message in client.receive_messages():
                if isinstance(message, AssistantMessage):
                    chunk_text = message.chunk.text if message.chunk else ""
                    print(chunk_text, end="", flush=True)
                
                elif isinstance(message, ToolCallMessage):
                    if message.status == ToolCallStatus.PENDING:
                        print(f"\n\n🔧 [工具调用开始] {message.tool_name}")
                        current_tool = message.tool_name
                        tool_calls_info.append({
                            "name": message.tool_name,
                            "status": "pending"
                        })
                    elif message.status == ToolCallStatus.IN_PROGRESS:
                        print(f"   ⏳ 执行中...")
                    elif message.status == ToolCallStatus.COMPLETED:
                        print(f"   ✅ 完成")
                        if message.result:
                            # 显示部分结果
                            result_str = str(message.result)
                            if len(result_str) > 500:
                                print(f"   结果预览: {result_str[:500]}...")
                            else:
                                print(f"   结果: {result_str}")
                    elif message.status == ToolCallStatus.FAILED:
                        print(f"   ❌ 失败: {message.error}")
                
                elif isinstance(message, TaskFinishMessage):
                    print(f"\n\n--- 任务结束 ---")
                    print(f"停止原因: {message.stop_reason}")
                    break
            
            print(f"\n工具调用统计: {len(tool_calls_info)} 次")
            for tc in tool_calls_info:
                print(f"  - {tc['name']}: {tc['status']}")
            
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_multiple_tools())
