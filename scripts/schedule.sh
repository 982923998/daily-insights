#!/bin/bash
# schedule.sh — 管理定时抓取任务（launchd）
#
# 任务说明：
#   AI 资讯       — 每天 08:00（fetch.sh ai）
#   Brain MRI     — 每天 08:30（fetch.sh brainmri）
#   学术文献      — 每 3 天（fetch.sh autism depression adhd ad pd）
#   Multi-Echo    — 每 7 天（fetch.sh mefmri）
#
# 用法:
#   ./scripts/schedule.sh install          # 安装全部定时任务
#   ./scripts/schedule.sh uninstall        # 卸载全部定时任务
#   ./scripts/schedule.sh status           # 查看状态
#   ./scripts/schedule.sh run-now ai       # 立即触发 AI 抓取
#   ./scripts/schedule.sh run-now brainmri # 立即触发 Brain MRI 抓取
#   ./scripts/schedule.sh run-now academic # 立即触发学术文献抓取
#   ./scripts/schedule.sh run-now mefmri   # 立即触发 ME-fMRI 抓取

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
FETCH_SCRIPT="$PROJECT_DIR/scripts/fetch.sh"

LABEL_AI="com.dailyinsights.fetch.ai"
LABEL_BRAINMRI="com.dailyinsights.fetch.brainmri"
LABEL_ACADEMIC="com.dailyinsights.fetch.academic"
LABEL_MEFMRI="com.dailyinsights.fetch.mefmri"
PLIST_AI="$HOME/Library/LaunchAgents/$LABEL_AI.plist"
PLIST_BRAINMRI="$HOME/Library/LaunchAgents/$LABEL_BRAINMRI.plist"
PLIST_ACADEMIC="$HOME/Library/LaunchAgents/$LABEL_ACADEMIC.plist"
PLIST_MEFMRI="$HOME/Library/LaunchAgents/$LABEL_MEFMRI.plist"

# 旧 plist 清理（从单域 autism 迁移到批量 academic）
LABEL_AUTISM_OLD="com.dailyinsights.fetch.autism"
PLIST_AUTISM_OLD="$HOME/Library/LaunchAgents/$LABEL_AUTISM_OLD.plist"

# ── 颜色输出 ─────────────────────────────────────────────
green()  { echo "\033[32m$*\033[0m"; }
red()    { echo "\033[31m$*\033[0m"; }
yellow() { echo "\033[33m$*\033[0m"; }

# ── 安装 ─────────────────────────────────────────────────
do_install() {
    OPENCODE_PATH=$(which opencode 2>/dev/null)
    if [ -z "$OPENCODE_PATH" ]; then
        red "[ERROR] 未找到 opencode，请先安装后重试"
        exit 1
    fi

    mkdir -p "$LOG_DIR"

    # 清理旧的单域 autism plist
    if [ -f "$PLIST_AUTISM_OLD" ]; then
        launchctl unload "$PLIST_AUTISM_OLD" 2>/dev/null || true
        rm "$PLIST_AUTISM_OLD"
    fi

    # --- AI 资讯：每天 08:00 ---
    cat > "$PLIST_AI" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL_AI}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${FETCH_SCRIPT}</string>
        <string>ai</string>
    </array>

    <!-- 每天 08:00 -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>   <integer>8</integer>
        <key>Minute</key> <integer>0</integer>
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
    <string>${LOG_DIR}/fetch-ai.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/fetch-ai.error.log</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF

    # --- Brain MRI：每天 08:30 ---
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

    <!-- 每天 08:30 -->
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

    # --- 学术文献（每 3 天 = 259200 秒）：autism depression adhd ad pd ---
    cat > "$PLIST_ACADEMIC" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL_ACADEMIC}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${FETCH_SCRIPT}</string>
        <string>autism</string>
        <string>depression</string>
        <string>adhd</string>
        <string>ad</string>
        <string>pd</string>
    </array>

    <!-- 每 3 天 = 259200 秒 -->
    <key>StartInterval</key>
    <integer>259200</integer>

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
    <string>${LOG_DIR}/fetch-academic.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/fetch-academic.error.log</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF

    # --- Multi-Echo fMRI 文献：每 7 天（604800 秒）---
    cat > "$PLIST_MEFMRI" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL_MEFMRI}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${FETCH_SCRIPT}</string>
        <string>mefmri</string>
    </array>

    <!-- 每 7 天 = 604800 秒 -->
    <key>StartInterval</key>
    <integer>604800</integer>

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
    <string>${LOG_DIR}/fetch-mefmri.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/fetch-mefmri.error.log</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF

    launchctl unload "$PLIST_AI"       2>/dev/null || true
    launchctl unload "$PLIST_BRAINMRI" 2>/dev/null || true
    launchctl unload "$PLIST_ACADEMIC" 2>/dev/null || true
    launchctl unload "$PLIST_MEFMRI"   2>/dev/null || true
    launchctl load "$PLIST_AI"
    launchctl load "$PLIST_BRAINMRI"
    launchctl load "$PLIST_ACADEMIC"
    launchctl load "$PLIST_MEFMRI"

    green "✅ 定时任务已安装"
    echo "   AI 资讯     — 每天 08:00                       日志：$LOG_DIR/fetch-ai.log"
    echo "   Brain MRI   — 每天 08:30                       日志：$LOG_DIR/fetch-brainmri.log"
    echo "   学术文献    — 每 3 天（ASD/抑郁/ADHD/AD/PD）   日志：$LOG_DIR/fetch-academic.log"
    echo "   ME-fMRI     — 每 7 天                          日志：$LOG_DIR/fetch-mefmri.log"
    echo ""
    yellow "   立即测试：./scripts/schedule.sh run-now ai"
    yellow "             ./scripts/schedule.sh run-now brainmri"
    yellow "             ./scripts/schedule.sh run-now academic"
    yellow "             ./scripts/schedule.sh run-now mefmri"
    yellow "   查看状态：./scripts/schedule.sh status"
}

# ── 卸载 ─────────────────────────────────────────────────
do_uninstall() {
    for plist in "$PLIST_AI" "$PLIST_BRAINMRI" "$PLIST_ACADEMIC" "$PLIST_MEFMRI" "$PLIST_AUTISM_OLD"; do
        if [ -f "$plist" ]; then
            launchctl unload "$plist" 2>/dev/null || true
            rm "$plist"
        fi
    done
    green "✅ 全部定时任务已卸载"
}

# ── 状态 ─────────────────────────────────────────────────
do_status() {
    for entry in \
        "${LABEL_AI}:AI 资讯（每天 08:00）:${LOG_DIR}/fetch-ai.log:${LOG_DIR}/fetch-ai.error.log" \
        "${LABEL_BRAINMRI}:Brain MRI（每天 08:30）:${LOG_DIR}/fetch-brainmri.log:${LOG_DIR}/fetch-brainmri.error.log" \
        "${LABEL_ACADEMIC}:学术文献（每 3 天）:${LOG_DIR}/fetch-academic.log:${LOG_DIR}/fetch-academic.error.log" \
        "${LABEL_MEFMRI}:ME-fMRI（每 7 天）:${LOG_DIR}/fetch-mefmri.log:${LOG_DIR}/fetch-mefmri.error.log"
    do
        label="${entry%%:*}"; rest="${entry#*:}"
        name="${rest%%:*}";   rest="${rest#*:}"
        log="${rest%%:*}";    errlog="${rest#*:}"

        echo "=== $name ($label) ==="
        result=$(launchctl list 2>/dev/null | grep "$label")
        if [ -n "$result" ]; then
            green "● 已加载：$result"
            pid=$(echo "$result" | awk '{print $1}')
            code=$(echo "$result" | awk '{print $2}')
            [ "$pid" != "-" ] && echo "  当前正在运行 (PID: $pid)" || echo "  当前未运行（等待下次触发）"
            [ "$code" != "0" ] && [ "$code" != "-" ] && red "  上次退出码：$code（异常）"
        else
            yellow "● 未加载（定时任务未安装）"
        fi

        echo ""
        echo "--- 最近日志（后10行）---"
        if [ -f "$log" ]; then
            tail -10 "$log"
        else
            echo "  （暂无日志）"
        fi

        if [ -s "$errlog" ]; then
            echo ""
            red "--- 错误日志 ---"
            tail -5 "$errlog"
        fi
        echo ""
    done
}

# ── 立即运行 ─────────────────────────────────────────────
do_run_now() {
    local target="${1:-}"
    local label="" name="" log=""
    case "$target" in
        ai)       label="$LABEL_AI";       name="AI";        log="$LOG_DIR/fetch-ai.log" ;;
        brainmri) label="$LABEL_BRAINMRI"; name="Brain MRI"; log="$LOG_DIR/fetch-brainmri.log" ;;
        academic) label="$LABEL_ACADEMIC"; name="学术文献";  log="$LOG_DIR/fetch-academic.log" ;;
        mefmri)   label="$LABEL_MEFMRI";   name="ME-fMRI";   log="$LOG_DIR/fetch-mefmri.log" ;;
        *)
            echo "用法: $(basename "$0") run-now [ai|brainmri|academic|mefmri]"
            exit 1
            ;;
    esac

    if ! launchctl list 2>/dev/null | grep -q "$label"; then
        red "[ERROR] $name 定时任务未安装，请先运行 install"; exit 1
    fi
    green "▶ 立即触发 $name 抓取..."
    launchctl start "$label"
    echo "日志：$log"
}

# ── 入口 ─────────────────────────────────────────────────
case "${1:-}" in
    install)   do_install   ;;
    uninstall) do_uninstall ;;
    status)    do_status    ;;
    run-now)   do_run_now "${2:-}" ;;
    *)
        echo "用法: $(basename "$0") [install|uninstall|status|run-now]"
        echo ""
        echo "  install            安装全部定时任务"
        echo "  uninstall          卸载全部定时任务"
        echo "  status             查看运行状态和最近日志"
        echo "  run-now ai         立即触发 AI 抓取"
        echo "  run-now brainmri   立即触发 Brain MRI 抓取"
        echo "  run-now academic   立即触发学术文献抓取（ASD/抑郁/ADHD/AD/PD）"
        echo "  run-now mefmri     立即触发 ME-fMRI 抓取"
        exit 1
        ;;
esac
