#!/usr/bin/env python3
"""测试 iflow-sdk 会话保持 - 多轮对话"""
import asyncio

async def receive_response(client):
    """接收完整响应的辅助函数"""
    from iflow_sdk import AssistantMessage, ToolCallMessage, TaskFinishMessage, ToolCallStatus
    
    full_text = ""
    async for message in client.receive_messages():
        if isinstance(message, AssistantMessage):
            chunk_text = message.chunk.text if message.chunk else ""
            full_text += chunk_text
            print(chunk_text, end="", flush=True)
        elif isinstance(message, ToolCallMessage):
            if message.status == ToolCallStatus.PENDING:
                print(f"\n[工具: {message.tool_name}]", end=" ")
        elif isinstance(message, TaskFinishMessage):
            break
    print()  # 换行
    return full_text


async def test_session():
    print("=" * 50)
    print("测试: 会话保持 - 多轮对话")
    print("=" * 50)
    
    from iflow_sdk import IFlowClient, IFlowOptions
    
    options = IFlowOptions(
        url="ws://localhost:8090/acp",
        auto_start_process=False,
        timeout=60.0
    )
    
    try:
        async with IFlowClient(options) as client:
            print("✓ 已连接\n")
            
            # 第一轮对话
            print("【第1轮】用户: 我的名字叫小明")
            await client.send_message("我的名字叫小明，请记住")
            print("助手: ", end="")
            await receive_response(client)
            
            # 第二轮对话 - 测试是否记住
            print("\n【第2轮】用户: 你还记得我的名字吗？")
            await client.send_message("你还记得我的名字吗？")
            print("助手: ", end="")
            await receive_response(client)
            
            # 第三轮对话 - 执行任务
            print("\n【第3轮】用户: 创建一个名为 hello.py 的文件，打印 Hello World")
            await client.send_message("创建一个名为 hello.py 的文件，打印 Hello World")
            print("助手: ", end="")
            await receive_response(client)
            
            # 第四轮对话 - 验证文件
            print("\n【第4轮】用户: 读取 hello.py 的内容")
            await client.send_message("读取 hello.py 的内容")
            print("助手: ", end="")
            await receive_response(client)
            
            print("\n--- 会话测试完成 ---")
            
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_session())
