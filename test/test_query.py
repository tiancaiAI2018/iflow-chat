#!/usr/bin/env python3
"""测试 iflow-sdk query 和 query_stream 函数"""
import asyncio

async def test_query():
    """测试 query 函数"""
    print("=" * 50)
    print("测试 1: query() 简单查询")
    print("=" * 50)
    
    from iflow_sdk import query
    
    try:
        response = await query("1+1等于几？")
        print(f"响应: {response}")
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")


async def test_query_stream():
    """测试 query_stream 函数"""
    print("\n" + "=" * 50)
    print("测试 2: query_stream() 流式响应")
    print("=" * 50)
    
    from iflow_sdk import query_stream
    
    try:
        print("响应: ", end="", flush=True)
        async for chunk in query_stream("请用一句话解释什么是Python"):
            print(chunk, end="", flush=True)
        print()  # 换行
    except Exception as e:
        print(f"\n错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def test_query_with_options():
    """测试带选项的 query"""
    print("\n" + "=" * 50)
    print("测试 3: query() 带自定义选项")
    print("=" * 50)
    
    from iflow_sdk import query, IFlowOptions
    
    options = IFlowOptions(
        url="ws://localhost:8090/acp",
        auto_start_process=False,
        timeout=30.0
    )
    
    try:
        response = await query("你好", options=options)
        print(f"响应: {response}")
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")


async def main():
    await test_query()
    await test_query_stream()
    await test_query_with_options()


if __name__ == "__main__":
    asyncio.run(main())
