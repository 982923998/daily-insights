#!/bin/bash
# schedule.sh — 管理本地三个活动领域的每日抓取任务（launchd）

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
FETCH_SCRIPT="$PROJECT_DIR/scripts/fetch.sh"

LABEL_ALL="com.dailyinsights.fetch.all"
PLIST_ALL="$HOME/Library/LaunchAgents/$LABEL_ALL.plist"
OLD_LABELS=(
    "com.dailyinsights.fetch.ai"
    "com.dailyinsights.fetch.academic"
    "com.dailyinsights.fetch.autism"
    "com.dailyinsights.fetch.mefmri"
    "com.dailyinsights.fetch.brainmri"
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

    cat > "$PLIST_ALL" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL_ALL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${FETCH_SCRIPT}</string>
        <string>all</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key> <integer>8</integer>
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
    <string>${LOG_DIR}/fetch-all.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/fetch-all.error.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF

    launchctl unload "$PLIST_ALL" 2>/dev/null || true
    if ! launchctl load "$PLIST_ALL"; then
        red "[ERROR] 定时任务加载失败"
        return 1
    fi
    green "定时任务已安装：每天 08:30 抓取 Autism + MRI、Depression + MRI、TMS"
    echo "日志：$LOG_DIR/fetch-all.log"
    yellow "立即测试：./scripts/schedule.sh run-now all"
}

do_uninstall() {
    cleanup_old_tasks
    if [ -f "$PLIST_ALL" ]; then
        launchctl unload "$PLIST_ALL" 2>/dev/null || true
        rm "$PLIST_ALL"
    fi
    green "定时任务已卸载"
}

do_status() {
    echo "=== Daily Insights ($LABEL_ALL) ==="
    if launchctl print "gui/$(id -u)/$LABEL_ALL" >/dev/null 2>&1; then
        green "已加载"
    else
        yellow "未加载（定时任务未安装）"
    fi
    echo "--- 最近日志（后10行）---"
    [ -f "$LOG_DIR/fetch-all.log" ] && tail -10 "$LOG_DIR/fetch-all.log" || echo "（暂无日志）"
    if [ -s "$LOG_DIR/fetch-all.error.log" ]; then
        red "--- 错误日志 ---"
        tail -5 "$LOG_DIR/fetch-all.error.log"
    fi
}

do_run_now() {
    local target="${1:-all}"
    if [ "$target" != "all" ]; then
        echo "用法: $(basename "$0") run-now all"
        exit 1
    fi
    if ! launchctl print "gui/$(id -u)/$LABEL_ALL" >/dev/null 2>&1; then
        red "[ERROR] 定时任务未安装，请先运行 install"
        exit 1
    fi
    green "立即触发三个领域抓取..."
    if ! launchctl start "$LABEL_ALL"; then
        red "[ERROR] 定时任务触发失败"
        return 1
    fi
    echo "日志：$LOG_DIR/fetch-all.log"
}

case "${1:-}" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
    status)    do_status ;;
    run-now)   do_run_now "${2:-all}" ;;
    *)
        echo "用法: $(basename "$0") [install|uninstall|status|run-now]"
        echo "  install       安装每日任务"
        echo "  uninstall     卸载每日任务"
        echo "  status        查看状态和日志"
        echo "  run-now all   立即触发三个领域抓取"
        exit 1
        ;;
esac
