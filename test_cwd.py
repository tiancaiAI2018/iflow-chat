"""
测试 iFlow SDK 的 cwd 参数行为
"""
import asyncio
import sys
sys.path.insert(0, '/root/.iflow-bot/workspace/mybot')

from iflow_sdk import IFlowClient, IFlowOptions
from iflow_sdk.types import AssistantMessage, TaskFinishMessage


async def test_cwd():
    """测试指定工作目录"""
    # 指定工作目录为 workspace 根目录
    cwd_path = "/root/.iflow-bot/workspace"
    
    options = IFlowOptions(
        auto_start_process=True,
        cwd=cwd_path,
        timeout=30.0,
    )
    
    print(f"正在连接 iFlow，指定工作目录: {cwd_path}")
    print(f"选项: auto_start_process={options.auto_start_process}, cwd={options.cwd}")
    
    async with IFlowClient(options) as client:
        print(f"已连接，发送消息...")
        
        # 询问工作目录
        message = "你当前的工作目录是啥"
        await client.send_message(message)
        
        print(f"用户: {message}")
        print("AI: ", end="", flush=True)
        
        async for msg in client.receive_messages():
            if isinstance(msg, AssistantMessage):
                print(msg.chunk.text, end="", flush=True)
            elif isinstance(msg, TaskFinishMessage):
                print()  # 换行
                print(f"任务完成，停止原因: {msg.stop_reason}")
                break


if __name__ == "__main__":
    asyncio.run(test_cwd())
