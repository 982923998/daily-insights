#!/bin/bash
# schedule.sh — 管理每日 08:00 自动抓取的 launchd 定时任务
# 用法:
#   ./scripts/schedule.sh install    # 安装定时任务
#   ./scripts/schedule.sh uninstall  # 卸载定时任务
#   ./scripts/schedule.sh status     # 查看状态
#   ./scripts/schedule.sh run-now    # 立即触发一次（测试用）

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.dailyinsights.fetch"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$PROJECT_DIR/logs"
FETCH_SCRIPT="$PROJECT_DIR/scripts/fetch.sh"

# ── 颜色输出 ─────────────────────────────────────────────
green()  { echo "\033[32m$*\033[0m"; }
red()    { echo "\033[31m$*\033[0m"; }
yellow() { echo "\033[33m$*\033[0m"; }

# ── 安装 ─────────────────────────────────────────────────
do_install() {
    # 检查 opencode
    OPENCODE_PATH=$(which opencode 2>/dev/null)
    if [ -z "$OPENCODE_PATH" ]; then
        red "[ERROR] 未找到 opencode，请先安装后重试"
        exit 1
    fi

    mkdir -p "$LOG_DIR"

    # 写 plist（展开变量，路径写死，launchd 环境无法用 ~）
    cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${FETCH_SCRIPT}</string>
        <string>all</string>
    </array>

    <!-- 每天 08:00 触发 -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>    <integer>8</integer>
        <key>Minute</key>  <integer>0</integer>
    </dict>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <!-- launchd 环境没有 PATH，需要手动指定 -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/fetch.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/fetch.error.log</string>

    <!-- 安装时不立即运行，等到 08:00 -->
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF

    # 重新加载（已存在则先卸载）
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"

    green "✅ 定时任务已安装"
    echo "   触发时间：每天 08:00"
    echo "   抓取内容：AI 资讯 + Autism 资讯"
    echo "   日志路径：$LOG_DIR/fetch.log"
    echo "   错误日志：$LOG_DIR/fetch.error.log"
    echo ""
    yellow "   立即测试：./scripts/schedule.sh run-now"
    yellow "   查看状态：./scripts/schedule.sh status"
}

# ── 卸载 ─────────────────────────────────────────────────
do_uninstall() {
    if [ ! -f "$PLIST" ]; then
        yellow "⚠️  未找到已安装的定时任务"
        exit 0
    fi
    launchctl unload "$PLIST" 2>/dev/null || true
    rm "$PLIST"
    green "✅ 定时任务已卸载"
}

# ── 状态 ─────────────────────────────────────────────────
do_status() {
    echo "=== launchd 状态 ==="
    result=$(launchctl list 2>/dev/null | grep "$LABEL")
    if [ -n "$result" ]; then
        green "● 已加载：$result"
        # 第一列是 PID（-表示未运行），第二列是最近退出码
        pid=$(echo "$result" | awk '{print $1}')
        code=$(echo "$result" | awk '{print $2}')
        [ "$pid" != "-" ] && echo "  当前正在运行 (PID: $pid)" || echo "  当前未运行（等待下次触发）"
        [ "$code" != "0" ] && [ "$code" != "-" ] && red "  上次退出码：$code（异常）"
    else
        yellow "● 未加载（定时任务未安装）"
    fi

    echo ""
    echo "=== 最近日志（后20行）==="
    if [ -f "$LOG_DIR/fetch.log" ]; then
        tail -20 "$LOG_DIR/fetch.log"
    else
        echo "  （暂无日志）"
    fi

    if [ -s "$LOG_DIR/fetch.error.log" ]; then
        echo ""
        red "=== 错误日志 ==="
        tail -10 "$LOG_DIR/fetch.error.log"
    fi
}

# ── 立即运行 ─────────────────────────────────────────────
do_run_now() {
    if ! launchctl list 2>/dev/null | grep -q "$LABEL"; then
        red "[ERROR] 定时任务未安装，请先运行 install"
        exit 1
    fi
    green "▶ 立即触发抓取任务..."
    launchctl start "$LABEL"
    echo "任务已在后台启动，日志：$LOG_DIR/fetch.log"
    echo "实时查看：tail -f $LOG_DIR/fetch.log"
}

# ── 入口 ─────────────────────────────────────────────────
case "${1:-}" in
    install)   do_install   ;;
    uninstall) do_uninstall ;;
    status)    do_status    ;;
    run-now)   do_run_now   ;;
    *)
        echo "用法: $(basename "$0") [install|uninstall|status|run-now]"
        echo ""
        echo "  install    安装定时任务（每天 08:00 自动抓取）"
        echo "  uninstall  卸载定时任务"
        echo "  status     查看运行状态和最近日志"
        echo "  run-now    立即触发一次（测试用）"
        exit 1
        ;;
esac
