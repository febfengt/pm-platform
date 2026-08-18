#!/usr/bin/env bash
# PM 私信平台 - 一键安装脚本
# 用法: curl -fsSL https://raw.githubusercontent.com/febfengt/pm-platform/main/install.sh | bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[✗]${NC} $*"; exit 1; }

install_dir="/root/pm_platform"
project="febfengt/pm-platform"
branch="main"

echo ""
echo "========================================"
echo "  PM 私信平台 - 一键安装"
echo "  https://github.com/febfengt/pm-platform"
echo "========================================"
echo ""

# ---------- 0. TTY 检测 ----------
if [ ! -t 0 ]; then
    echo -e "${YELLOW}[!]${NC} 检测到管道模式，交互输入不可用。"
    echo ""
    echo "  请改用以下两种方式之一："
    echo ""
    echo "  方式1 (下载后执行):"
    echo "    curl -fsSL https://raw.githubusercontent.com/febfengt/pm-platform/main/install.sh -o install.sh"
    echo "    bash install.sh"
    echo ""
    echo "  方式2 (环境变量):"
    echo "    PM_TOKEN=你的token PM_ADMIN=你的UID bash install.sh"
    echo "    curl -fsSL URL | PM_TOKEN=xxx PM_ADMIN=yyy bash"
    echo ""
    # 如果环境变量提供了就继续
    if [ -n "${PM_TOKEN:-}" ] && [ -n "${PM_ADMIN:-}" ]; then
        info "通过环境变量检测到配置，继续安装..."
    else
        err ""
    fi
fi

# ---------- 1. 依赖检测 ----------
echo "--- 检查环境 ---"
for cmd in curl git python3 systemctl; do
    command -v "$cmd" &>/dev/null || err "缺少依赖: $cmd，请先安装"
done
info "基础依赖 OK"

python3 -c "import json, os, threading" &>/dev/null || err "缺少标准库"
info "Python 标准库 OK"

# aiogram
python3 -c "import aiogram; print(aiogram.__version__)" &>/dev/null && {
    info "aiogram 已安装 ($(python3 -c 'import aiogram; print(aiogram.__version__)'))"
} || {
    warn "安装 aiogram>=3.30..."
    if python3 -m pip install "aiogram>=3.30" --quiet 2>/dev/null; then
        info "aiogram 安装成功 ($(python3 -c 'import aiogram; print(aiogram.__version__)'))"
    elif python3 -m pip install "aiogram>=3.30" --break-system-packages --quiet 2>/dev/null; then
        info "aiogram 安装成功 ($(python3 -c 'import aiogram; print(aiogram.__version__)')) (break-system-packages)"
    else
        err "aiogram 安装失败，请手动: pip install 'aiogram>=3.30'"
    fi
}

# ---------- 2. 下载/更新 ----------
if [ -d "$install_dir/.git" ]; then
    warn "目录已存在，执行 git pull 更新..."
    cd "$install_dir"
    git pull origin "$branch" || warn "pull 失败，尝试重新clone"
    cd - &>/dev/null
else
    info "正在克隆仓库..."
    git clone -b "$branch" "https://github.com/$project" "$install_dir" || err "克隆失败"
fi
info "代码已就绪: $install_dir"

# ---------- 3. 配置确认 ----------
echo ""
echo "--- 平台配置 ---"

token="${PM_TOKEN:-}"
if [ -z "$token" ] && [ -f "$install_dir/config.py" ]; then
    token=$(grep -oP 'PLATFORM_BOT_TOKEN\s*=\s*"\K[^"]+' "$install_dir/config.py" 2>/dev/null || true)
fi
if [ -z "$token" ] || [ "$token" = "YOUR_TOKEN_HERE" ]; then
    if [ -t 0 ]; then
        read -rp "  平台 Bot Token (从 @BotFather 获取): " token
    else
        err "Token 未提供。使用 PM_TOKEN 环境变量或下载脚本后交互输入"
    fi
    [ -z "$token" ] && err "Token 不能为空"
fi
info "Token 已填写 (${token:0:8}...)"

admin_id="${PM_ADMIN:-}"
if [ -z "$admin_id" ] && [ -t 0 ]; then
    read -rp "  平台管理员 UID (留空默认 7743246793): " admin_id
fi
[ -z "$admin_id" ] && admin_id="7743246793"
info "管理员 UID: $admin_id"

# 写入 config.py
cat > "$install_dir/config.py" << CFGEOF
# PM 私信平台 - 配置
import os

# 平台bot的token
PLATFORM_BOT_TOKEN = "$token"

# 平台管理员
PLATFORM_ADMIN_IDS = [$admin_id]

# 路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(BASE_DIR, "bot_registry.json")
DATA_DIR = os.path.join(BASE_DIR, "bot_data")
CFGEOF
info "config.py 已写入"

# ---------- 4. systemd 服务 ----------
cat > /tmp/pm-platform.service << SVCEOF
[Unit]
Description=PM 私信平台
After=network.target

[Service]
Type=simple
WorkingDirectory=$install_dir
ExecStart=/usr/bin/python3 $install_dir/platform_bot.py
Restart=always
RestartSec=3
TimeoutStopSec=15
StandardOutput=append:$install_dir/logs/platform.log
StandardError=append:$install_dir/logs/platform.log

[Install]
WantedBy=multi-user.target
SVCEOF

install -m 644 /tmp/pm-platform.service /etc/systemd/system/pm-platform.service
rm -f /tmp/pm-platform.service
systemctl daemon-reload
info "systemd 服务已安装"

# ---------- 5. 目录 & 权限 ----------
mkdir -p "$install_dir/bot_data" "$install_dir/logs"
chmod 700 "$install_dir"
info "目录已就绪"

# ---------- 6. 启动 ----------
echo ""
echo "--- 启动 ---"
systemctl restart pm-platform
sleep 3
if systemctl is-active --quiet pm-platform; then
    info "pm-platform 已启动并运行"
else
    warn "服务可能未正常启动，查看日志:"
    journalctl -u pm-platform --no-pager -n 10 2>/dev/null || cat "$install_dir/logs/platform.log" 2>/dev/null | tail -10
fi

# ---------- 7. 完成 ----------
echo ""
echo "========================================"
echo "  安装完成！"
echo "========================================"
echo ""
echo "  目录:   $install_dir"
echo "  服务:   pm-platform.service"
echo "  日志:   $install_dir/logs/platform.log"
echo ""
echo "  常用命令:"
echo "    systemctl status pm-platform   # 查看状态"
echo "    systemctl restart pm-platform  # 重启"
echo "    journalctl -u pm-platform -f   # 实时日志"
echo "    $install_dir/logs/platform.log     # 日志文件"
echo ""
echo "  平台 Bot 测试:"
echo "    在 Telegram 跟你的平台 Bot 发 /start"
echo "    注册子 Bot: /register → 发送 bot token"
echo ""