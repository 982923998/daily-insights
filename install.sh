#!/bin/bash
# install.sh — 在新电脑上一键完成安装，并在桌面创建启动图标
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="每日资讯.app"
DESKTOP="$HOME/Desktop"
APP_PATH="$DESKTOP/$APP_NAME"

echo "==================================="
echo "  每日资讯 · 安装向导"
echo "==================================="

# ── 1. 检查系统 ───────────────────────
if [[ "$(uname)" != "Darwin" ]]; then
    echo "[ERROR] 此脚本仅支持 macOS"
    exit 1
fi

# ── 2. 检查依赖 ───────────────────────
echo ""
echo "▶ 检查依赖..."

check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        echo "  [✗] 未找到 $1 — $2"
        MISSING=1
    else
        echo "  [✓] $1"
    fi
}

MISSING=0
check_cmd python3  "请安装 Python 3.8+: https://www.python.org"
check_cmd node     "请安装 Node.js 18+: https://nodejs.org"
check_cmd opencode "请安装 opencode: https://opencode.ai"

if [[ $MISSING -eq 1 ]]; then
    echo ""
    echo "[ERROR] 请先安装以上缺失依赖后重新运行此脚本。"
    exit 1
fi

# ── 3. 给脚本加执行权限 ───────────────
echo ""
echo "▶ 设置脚本权限..."
chmod +x "$PROJECT_DIR/scripts/fetch.sh"
echo "  [✓] scripts/fetch.sh"

# ── 4. 创建 AppleScript .app ──────────
echo ""
echo "▶ 创建桌面启动图标..."

cat > /tmp/daily_launcher.applescript << APPLESCRIPT
set projectDir to "$PROJECT_DIR"
set isRunning to do shell script "lsof -ti tcp:8080 >/dev/null 2>&1 && echo yes || echo no"
if isRunning is "no" then
    do shell script "cd " & quoted form of projectDir & " && nohup python3 scripts/server.py >/tmp/daily-insights.log 2>&1 &"
    delay 2
end if
open location "http://localhost:8080"
APPLESCRIPT

osacompile -o "$APP_PATH" /tmp/daily_launcher.applescript 2>/dev/null
echo "  [✓] $APP_NAME 已创建"

# ── 5. 生成并应用图标 ─────────────────
echo ""
echo "▶ 生成应用图标..."

python3 << 'PYEOF'
import sys
try:
    from AppKit import (NSImage, NSAttributedString, NSFont, NSColor,
                        NSBezierPath, NSBitmapImageRep, NSFontAttributeName, NSPNGFileType)
    from Foundation import NSMakeRect, NSMakeSize, NSMakePoint

    size = 1024
    image = NSImage.alloc().initWithSize_(NSMakeSize(size, size))
    image.lockFocus()

    NSColor.colorWithSRGBRed_green_blue_alpha_(0.05, 0.07, 0.18, 1.0).setFill()
    path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(0, 0, size, size), 220, 220
    )
    path.fill()

    font = NSFont.systemFontOfSize_(600)
    attrs = {NSFontAttributeName: font}
    s = NSAttributedString.alloc().initWithString_attributes_('📰', attrs)
    tw = s.size().width
    th = s.size().height
    s.drawAtPoint_(NSMakePoint((size - tw) / 2, (size - th) / 2 + 40))

    image.unlockFocus()

    tiff = image.TIFFRepresentation()
    rep = NSBitmapImageRep.imageRepWithData_(tiff)
    data = rep.representationUsingType_properties_(NSPNGFileType, None)
    data.writeToFile_atomically_('/tmp/daily_icon.png', True)
    print("  [✓] 图标已生成")
except Exception as e:
    print(f"  [!] 图标生成失败（{e}），将使用默认图标")
    sys.exit(0)
PYEOF

# 如果 PNG 生成成功，转换为 icns 并应用
if [[ -f /tmp/daily_icon.png ]]; then
    mkdir -p /tmp/daily.iconset
    for res in 16 32 64 128 256 512 1024; do
        sips -z $res $res /tmp/daily_icon.png \
            --out /tmp/daily.iconset/icon_${res}x${res}.png >/dev/null 2>&1
    done
    sips -z 32   32   /tmp/daily_icon.png --out /tmp/daily.iconset/icon_16x16@2x.png   >/dev/null 2>&1
    sips -z 64   64   /tmp/daily_icon.png --out /tmp/daily.iconset/icon_32x32@2x.png   >/dev/null 2>&1
    sips -z 256  256  /tmp/daily_icon.png --out /tmp/daily.iconset/icon_128x128@2x.png >/dev/null 2>&1
    sips -z 512  512  /tmp/daily_icon.png --out /tmp/daily.iconset/icon_256x256@2x.png >/dev/null 2>&1
    sips -z 1024 1024 /tmp/daily_icon.png --out /tmp/daily.iconset/icon_512x512@2x.png >/dev/null 2>&1

    iconutil -c icns /tmp/daily.iconset -o /tmp/daily.icns 2>/dev/null
    cp /tmp/daily.icns "$APP_PATH/Contents/Resources/applet.icns"
    touch "$APP_PATH"
    echo "  [✓] 图标已应用"

    # 清理临时文件
    rm -rf /tmp/daily.iconset /tmp/daily_icon.png /tmp/daily.icns /tmp/daily_launcher.applescript
fi

# ── 6. 完成 ───────────────────────────
echo ""
echo "==================================="
echo "  ✅ 安装完成！"
echo ""
echo "  桌面已创建「每日资讯」图标"
echo "  首次双击时 macOS 会提示安全确认"
echo "  右键 → 打开 → 打开 即可"
echo "==================================="
