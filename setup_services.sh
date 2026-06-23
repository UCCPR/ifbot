#!/bin/bash
# QQ Bot 服务器部署脚本 - 安装为系统服务
set -e

echo "============================================"
echo "  QQ Bot 生产环境部署"
echo "============================================"

# 检查 cloudflared
if ! command -v cloudflared &>/dev/null; then
    echo "安装 cloudflared..."
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
fi

cd /home/root/zmdbot
mkdir -p static_images

# 1. 清理旧版本残留
echo "[1/3] 清理旧服务..."
systemctl stop qqbot.service qqbot-tunnel.service 2>/dev/null || true
systemctl stop qqbot-image 2>/dev/null && echo "  已停止旧 qqbot-image" || true
systemctl disable qqbot-image 2>/dev/null || true
rm -f /etc/systemd/system/qqbot-image.service
fuser -k 18080/tcp 2>/dev/null && echo "  已释放端口 18080" || true
systemctl daemon-reload

# 安装新服务（如果还没装）
cp -f qqbot-tunnel.service /etc/systemd/system/
cp -f qqbot.service /etc/systemd/system/
systemctl daemon-reload

# 2. 启动 Bot（HTTP 服务先占住 18080）
echo "[2/3] 启动 Bot..."
systemctl enable --now qqbot.service
sleep 3
if ! systemctl is-active --quiet qqbot.service; then
    echo "  ✗ Bot 启动失败！"
    journalctl -u qqbot.service --no-pager -n 15
    exit 1
fi
echo "  Bot 已启动"

# 3. 启动隧道 + 安装看门狗
echo "[3/3] 启动隧道..."
# 使用 systemd 管理（Restart=always 崩溃自重启）
systemctl stop qqbot-tunnel.service 2>/dev/null || true
pkill -f "cloudflared.*18080" 2>/dev/null || true
sleep 1

systemctl enable --now qqbot-tunnel.service
echo "  隧道服务已启动"

# 等待 URL 出现
TUNNEL_LOG="/tmp/qqbot_tunnel_init.log"
FOUND=""
echo "  等待隧道 URL..."
for i in $(seq 1 30); do
    sleep 2
    URL=$(journalctl -u qqbot-tunnel.service --since "1 min ago" --no-pager 2>/dev/null | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
    if [ -n "$URL" ]; then
        HOST=$(echo "$URL" | sed 's|^https://||')
        echo "  隧道地址: $URL"
        sed -i "s|IMAGE_HOST = \".*\"|IMAGE_HOST = \"$HOST\"|" /home/root/zmdbot/config.py
        echo "  已更新 config.py"
        FOUND="$HOST"
        break
    fi
    printf "."
done
echo ""

if [ -z "$FOUND" ]; then
    echo "  ⚠ 隧道地址获取超时，稍后 watchdog_tunnel.sh 会自动修复"
else
    echo "  隧道就绪: $FOUND"
fi

echo ""
echo "============================================"
echo "  部署完成！"
echo "  Bot:    systemctl status qqbot"
echo "  隧道:   systemctl status qqbot-tunnel"
echo "============================================"
