#!/bin/bash
# schedule.sh — 管理本地 Brain MRI 定时抓取任务（launchd）
#
# 用法:
#   ./scripts/schedule.sh install          # 安装 Brain MRI 定时任务
#   ./scripts/schedule.sh uninstall        # 卸载定时任务
#   ./scripts/schedule.sh status           # 查看状态
#   ./scripts/schedule.sh run-now brainmri # 立即触发 Brain MRI 抓取

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
FETCH_SCRIPT="$PROJECT_DIR/scripts/fetch.sh"

LABEL_BRAINMRI="com.dailyinsights.fetch.brainmri"
PLIST_BRAINMRI="$HOME/Library/LaunchAgents/$LABEL_BRAINMRI.plist"

OLD_LABELS=(
    "com.dailyinsights.fetch.ai"
    "com.dailyinsights.fetch.academic"
    "com.dailyinsights.fetch.autism"
    "com.dailyinsights.fetch.mefmri"
)

green()  { printf "\033[32m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

cleanup_old_tasks() {
    local label plist
    for label in "${OLD_LABELS[@]}"; do
        plist="$HOME/Library/LaunchAgents/$label.plist"
        if [ -f "$plist" ]; then
            launchctl unload "$plist" 2>/dev/null || true
            rm "$plist"
        fi
    done
}

do_install() {
    if ! command -v codex >/dev/null 2>&1; then
        red "[ERROR] 未找到 codex，请先安装后重试"
        exit 1
    fi

    mkdir -p "$LOG_DIR"
    cleanup_old_tasks

    cat > "$PLIST_BRAINMRI" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL_BRAINMRI}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${FETCH_SCRIPT}</string>
        <string>brainmri</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>   <integer>8</integer>
        <key>Minute</key> <integer>30</integer>
    </dict>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/fetch-brainmri.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/fetch-brainmri.error.log</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF

    launchctl unload "$PLIST_BRAINMRI" 2>/dev/null || true
    launchctl load "$PLIST_BRAINMRI"

    green "定时任务已安装"
    echo "   Brain MRI — 每天 08:30，抓取后自动分流到疾病标签"
    echo "   日志：$LOG_DIR/fetch-brainmri.log"
    echo ""
    yellow "   立即测试：./scripts/schedule.sh run-now brainmri"
    yellow "   查看状态：./scripts/schedule.sh status"
}

do_uninstall() {
    cleanup_old_tasks
    if [ -f "$PLIST_BRAINMRI" ]; then
        launchctl unload "$PLIST_BRAINMRI" 2>/dev/null || true
        rm "$PLIST_BRAINMRI"
    fi
    green "定时任务已卸载"
}

do_status() {
    echo "=== Brain MRI ($LABEL_BRAINMRI) ==="
    result=$(launchctl list 2>/dev/null | grep "$LABEL_BRAINMRI")
    if [ -n "$result" ]; then
        green "已加载：$result"
        pid=$(echo "$result" | awk '{print $1}')
        code=$(echo "$result" | awk '{print $2}')
        [ "$pid" != "-" ] && echo "  当前正在运行 (PID: $pid)" || echo "  当前未运行（等待下次触发）"
        [ "$code" != "0" ] && [ "$code" != "-" ] && red "  上次退出码：$code（异常）"
    else
        yellow "未加载（定时任务未安装）"
    fi

    echo ""
    echo "--- 最近日志（后10行）---"
    if [ -f "$LOG_DIR/fetch-brainmri.log" ]; then
        tail -10 "$LOG_DIR/fetch-brainmri.log"
    else
        echo "  （暂无日志）"
    fi

    if [ -s "$LOG_DIR/fetch-brainmri.error.log" ]; then
        echo ""
        red "--- 错误日志 ---"
        tail -5 "$LOG_DIR/fetch-brainmri.error.log"
    fi
}

do_run_now() {
    local target="${1:-brainmri}"
    if [ "$target" != "brainmri" ]; then
        echo "用法: $(basename "$0") run-now brainmri"
        exit 1
    fi
    if ! launchctl list 2>/dev/null | grep -q "$LABEL_BRAINMRI"; then
        red "[ERROR] Brain MRI 定时任务未安装，请先运行 install"
        exit 1
    fi
    green "立即触发 Brain MRI 抓取..."
    launchctl start "$LABEL_BRAINMRI"
    echo "日志：$LOG_DIR/fetch-brainmri.log"
}

case "${1:-}" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
    status)    do_status ;;
    run-now)   do_run_now "${2:-brainmri}" ;;
    *)
        echo "用法: $(basename "$0") [install|uninstall|status|run-now]"
        echo ""
        echo "  install            安装 Brain MRI 定时任务"
        echo "  uninstall          卸载定时任务"
        echo "  status             查看运行状态和最近日志"
        echo "  run-now brainmri   立即触发 Brain MRI 抓取"
        exit 1
        ;;
esac
