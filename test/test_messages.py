#!/usr/bin/env python3
"""测试 iflow-sdk IFlowClient 消息类型"""
import asyncio

async def test_message_types():
    print("=" * 50)
    print("测试: IFlowClient 消息类型")
    print("=" * 50)
    
    from iflow_sdk import (
        IFlowClient, IFlowOptions,
        AssistantMessage, ToolCallMessage, PlanMessage, TaskFinishMessage,
        ToolCallStatus
    )
    
    options = IFlowOptions(
        url="ws://localhost:8090/acp",
        auto_start_process=False,
        timeout=60.0
    )
    
    try:
        async with IFlowClient(options) as client:
            print("✓ 已连接")
            
            # 发送一个需要工具调用的请求
            await client.send_message("请列出当前目录的文件")
            print("✓ 消息已发送")
            
            print("\n--- 接收消息 ---")
            full_text = ""
            tool_calls = []
            
            async for message in client.receive_messages():
                msg_type = type(message).__name__
                
                if isinstance(message, AssistantMessage):
                    # AI 助手的文本响应
                    chunk_text = message.chunk.text if message.chunk else ""
                    full_text += chunk_text
                    print(chunk_text, end="", flush=True)
                    
                    if message.agent_id:
                        print(f"\n[来自代理: {message.agent_id}]")
                
                elif isinstance(message, ToolCallMessage):
                    # 工具调用消息
                    print(f"\n\n[工具调用]")
                    print(f"  工具名: {message.tool_name}")
                    print(f"  状态: {message.status}")
                    
                    if message.status == ToolCallStatus.PENDING:
                        print(f"  等待中...")
                    elif message.status == ToolCallStatus.IN_PROGRESS:
                        print(f"  执行中...")
                    elif message.status == ToolCallStatus.COMPLETED:
                        result = message.result
                        if result:
                            result_str = str(result)[:300]
                            print(f"  结果: {result_str}...")
                    elif message.status == ToolCallStatus.FAILED:
                        print(f"  失败: {message.error}")
                    
                    tool_calls.append(message)
                
                elif isinstance(message, PlanMessage):
                    # 任务计划消息
                    print(f"\n\n[任务计划]")
                    for entry in message.entries:
                        status_icon = "✅" if entry.status == "completed" else "⏳"
                        print(f"  {status_icon} [{entry.priority}] {entry.content}")
                
                elif isinstance(message, TaskFinishMessage):
                    # 任务完成消息
                    print(f"\n\n[任务完成]")
                    print(f"  停止原因: {message.stop_reason}")
                    break
            
            print(f"\n\n--- 总结 ---")
            print(f"完整响应长度: {len(full_text)} 字符")
            print(f"工具调用次数: {len(tool_calls)}")
            
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_message_types())