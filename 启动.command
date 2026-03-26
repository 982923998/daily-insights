#!/bin/bash
# 双击此文件即可启动每日资讯项目并打开网页

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8080
HEALTH_URL="http://localhost:$PORT/api/domains"
WEB_URL="http://localhost:$PORT"
SERVER_LOG="$PROJECT_DIR/logs/server.log"

is_server_ready() {
    curl -fsS --max-time 1 "$HEALTH_URL" >/dev/null 2>&1
}

echo "==================================="
echo "  每日资讯 · Daily Insights"
echo "==================================="

# 检查是否已在运行（通过健康检查确认）
if is_server_ready; then
    echo "✅ 服务已在运行，直接打开网页..."
    open "$WEB_URL"
    exit 0
fi

# 端口被占用但健康检查失败，说明不是当前服务
if lsof -tiTCP:$PORT -sTCP:LISTEN &>/dev/null; then
    echo "❌ 端口 $PORT 已被其他程序占用，无法启动 Daily Insights。"
    echo "请先释放端口后重试：lsof -nP -iTCP:$PORT -sTCP:LISTEN"
    exit 1
fi

echo "⚡ 启动服务器..."
cd "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/logs"
python3 -u scripts/server.py >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

# 等待服务器就绪（最多10秒）
for i in $(seq 1 20); do
    if is_server_ready; then
        break
    fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        break
    fi
    sleep 0.5
done

if is_server_ready; then
    echo "🌐 打开网页..."
    open "$WEB_URL"
    echo ""
    echo "服务运行中，关闭此窗口将停止服务。"
    echo "-----------------------------------"
    wait $SERVER_PID
    exit $?
fi

echo "❌ 服务启动失败，未通过健康检查。"
if [ -f "$SERVER_LOG" ]; then
    echo "最近日志（$SERVER_LOG）："
    tail -n 40 "$SERVER_LOG"
fi
exit 1
