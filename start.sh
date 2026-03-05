#!/bin/bash

# mybot 前后端启动脚本
# 用法: ./start.sh [start|stop|status|restart]

PROJECT_DIR="/root/.iflow-bot/workspace/mybot"
BACKEND_LOG="$PROJECT_DIR/backend.log"
FRONTEND_LOG="$PROJECT_DIR/frontend.log"
BACKEND_PORT=8000
FRONTEND_PORT=3000

start_backend() {
    echo "启动后端服务..."
    cd "$PROJECT_DIR"
    nohup python3.12 -m uvicorn backend.main:app --host 0.0.0.0 --port $BACKEND_PORT > "$BACKEND_LOG" 2>&1 &
    sleep 3
    if curl -s http://localhost:$BACKEND_PORT/docs -o /dev/null 2>/dev/null; then
        echo "✅ 后端服务启动成功 (端口 $BACKEND_PORT)"
        echo "   API 文档: http://localhost:$BACKEND_PORT/docs"
    else
        echo "❌ 后端服务启动失败，查看日志: $BACKEND_LOG"
    fi
}

start_frontend() {
    echo "启动前端服务..."
    cd "$PROJECT_DIR/frontend"
    nohup npm start > "$FRONTEND_LOG" 2>&1 &
    sleep 5
    if curl -s http://localhost:$FRONTEND_PORT -o /dev/null 2>/dev/null; then
        echo "✅ 前端服务启动成功 (端口 $FRONTEND_PORT)"
        echo "   访问地址: http://localhost:$FRONTEND_PORT"
    else
        echo "⚠️ 前端服务正在启动中，请稍后访问..."
    fi
}

stop_backend() {
    echo "停止后端服务..."
    pkill -f "uvicorn backend.main:app" 2>/dev/null
    echo "✅ 后端服务已停止"
}

stop_frontend() {
    echo "停止前端服务..."
    pkill -f "react-scripts start" 2>/dev/null
    echo "✅ 前端服务已停止"
}

check_status() {
    echo "检查服务状态..."
    echo ""
    
    # 检查后端
    if curl -s http://localhost:$BACKEND_PORT/docs -o /dev/null 2>/dev/null; then
        echo "✅ 后端服务运行中 (端口 $BACKEND_PORT)"
    else
        echo "❌ 后端服务未运行"
    fi
    
    # 检查前端
    if curl -s http://localhost:$FRONTEND_PORT -o /dev/null 2>/dev/null; then
        echo "✅ 前端服务运行中 (端口 $FRONTEND_PORT)"
    else
        echo "❌ 前端服务未运行"
    fi
}

case "$1" in
    start)
        start_backend
        start_frontend
        ;;
    stop)
        stop_backend
        stop_frontend
        ;;
    restart)
        stop_backend
        stop_frontend
        sleep 2
        start_backend
        start_frontend
        ;;
    status)
        check_status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        echo ""
        echo "命令说明:"
        echo "  start   - 启动前后端服务"
        echo "  stop    - 停止前后端服务"
        echo "  restart - 重启前后端服务"
        echo "  status  - 检查服务运行状态"
        exit 1
        ;;
esac
