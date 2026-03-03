#!/usr/bin/env python3
"""测试 iflow-sdk 同步调用和错误处理"""
import time

def test_sync_query():
    """测试同步调用"""
    print("=" * 50)
    print("测试: query_sync 同步调用")
    print("=" * 50)
    
    from iflow_sdk import query_sync, IFlowOptions
    
    options = IFlowOptions(
        url="ws://localhost:8090/acp",
        auto_start_process=False,
        timeout=30.0
    )
    
    try:
        start = time.time()
        response = query_sync("计算 2+2 等于几？", options=options)
        elapsed = time.time() - start
        
        print(f"响应: {response}")
        print(f"耗时: {elapsed:.2f}秒")
        
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")


def test_error_handling():
    """测试错误处理"""
    print("\n" + "=" * 50)
    print("测试: 错误处理")
    print("=" * 50)
    
    from iflow_sdk import query_sync, IFlowOptions, TimeoutError, ConnectionError
    
    # 测试超时
    print("\n1. 测试超时 (设置1秒超时)...")
    options = IFlowOptions(
        url="ws://localhost:8090/acp",
        auto_start_process=False,
        timeout=1.0
    )
    try:
        response = query_sync("请详细解释量子计算的历史和发展", options=options)
        print(f"响应: {response}")
    except TimeoutError as e:
        print(f"✓ 捕获到超时错误: {e}")
    except Exception as e:
        print(f"其他错误: {type(e).__name__}: {e}")


def test_sdk_version():
    """打印 SDK 版本信息"""
    print("\n" + "=" * 50)
    print("SDK 信息")
    print("=" * 50)
    
    import iflow_sdk
    print(f"版本: {iflow_sdk.__version__}")
    print(f"协议版本: {iflow_sdk.PROTOCOL_VERSION}")
    
    # 列出所有导出的类和函数
    print("\n导出的符号:")
    for name in iflow_sdk.__all__ if hasattr(iflow_sdk, '__all__') else dir(iflow_sdk):
        if not name.startswith('_'):
            obj = getattr(iflow_sdk, name)
            obj_type = type(obj).__name__
            print(f"  - {name}: {obj_type}")


if __name__ == "__main__":
    test_sync_query()
    test_error_handling()
    test_sdk_version()
