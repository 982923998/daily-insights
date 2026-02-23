#!/bin/bash
# 双击此文件即可启动每日资讯项目并打开网页

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8080

echo "==================================="
echo "  每日资讯 · Daily Insights"
echo "==================================="

# 检查端口是否已被占用（服务已在运行）
if lsof -ti tcp:$PORT &>/dev/null; then
    echo "✅ 服务已在运行，直接打开网页..."
    open "http://localhost:$PORT"
    exit 0
fi

echo "⚡ 启动服务器..."
cd "$PROJECT_DIR"
python3 scripts/server.py &
SERVER_PID=$!

# 等待服务器就绪（最多10秒）
for i in $(seq 1 20); do
    if curl -s "http://localhost:$PORT" &>/dev/null; then
        break
    fi
    sleep 0.5
done

echo "🌐 打开网页..."
open "http://localhost:$PORT"

echo ""
echo "服务运行中，关闭此窗口将停止服务。"
echo "-----------------------------------"

# 等待服务器进程结束
wait $SERVER_PID
