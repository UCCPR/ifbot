#!/bin/bash
# QQ Bot 服务器部署脚本 - 安装为系统服务
set -e

echo "============================================"
echo "  QQ Bot 生产环境部署"
echo "============================================"

cd /home/root/zmdbot
mkdir -p static_images
# 从 config.py 解析 IMAGE_HOST（grep 解析，不依赖 python3 环境，与 Bot 运行时 _get_image_base_url 一致）
CONFIGURED_HOST=""
if [ -f config.py ]; then
    while IFS= read -r line; do
        if [[ "$line" =~ ^[[:space:]]*IMAGE_HOST[[:space:]]*=[[:space:]]*[\"\']([^\"\']*)[\"\'] ]]; then
            CONFIGURED_HOST="${BASH_REMATCH[1]}"
            break
        fi
    done < config.py
fi
USE_QUICK_TUNNEL=1
case "$CONFIGURED_HOST" in
    ""|localhost*|*.trycloudflare.com) ;;
    *) USE_QUICK_TUNNEL=0 ;;
esac

# 只有没有固定图片域名时才需要 Quick Tunnel。
if [ "$USE_QUICK_TUNNEL" -eq 1 ] && ! command -v cloudflared &>/dev/null; then
    echo "安装 cloudflared..."
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
fi

# 1. 清理旧版本残留
echo "[1/3] 清理旧服务..."
systemctl stop qqbot.service qqbot-tunnel.service 2>/dev/null || true
systemctl stop qqbot-image 2>/dev/null && echo "  已停止旧 qqbot-image" || true
systemctl disable qqbot-image 2>/dev/null || true
rm -f /etc/systemd/system/qqbot-image.service
fuser -k 18080/tcp 2>/dev/null && echo "  已释放端口 18080" || true
systemctl daemon-reload

# 安装新服务（如果还没装）
if [ "$USE_QUICK_TUNNEL" -eq 1 ]; then
    cp -f qqbot-tunnel.service /etc/systemd/system/
fi
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

# 3. 固定图床优先；仅在未配置固定域名时启动 Quick Tunnel。
if [ "$USE_QUICK_TUNNEL" -eq 0 ]; then
    systemctl disable --now qqbot-tunnel.service 2>/dev/null || true
    echo "[3/3] 使用固定图片域名: $CONFIGURED_HOST"
    FIXED_URL="$CONFIGURED_HOST"
    case "$FIXED_URL" in http://*|https://*) ;; *) FIXED_URL="https://$FIXED_URL" ;; esac
    if curl -fsSI --max-time 10 "$FIXED_URL/" >/dev/null 2>&1; then
        echo "  固定图床连通正常"
    else
        echo "  ⚠ 固定图床当前无法访问"
        echo "  请确认 Cloudflare named tunnel/反向代理正在运行，并指向 http://localhost:18080"
    fi
else
    echo "[3/3] 启动临时隧道..."
    systemctl stop qqbot-tunnel.service 2>/dev/null || true
    pkill -f "cloudflared.*18080" 2>/dev/null || true
    sleep 1

    systemctl enable --now qqbot-tunnel.service
    echo "  隧道服务已启动"

    FOUND=""
    echo "  等待隧道 URL..."
    for i in $(seq 1 30); do
        sleep 2
        URL=$(journalctl -u qqbot-tunnel.service --since "1 min ago" --no-pager 2>/dev/null | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
        if [ -n "$URL" ]; then
            HOST=$(echo "$URL" | sed 's|^https://||')
            echo "  临时隧道地址: $URL"
            sed -i "s|^[[:space:]]*IMAGE_HOST = [\"'].*|IMAGE_HOST = \"$HOST\"|" /home/root/zmdbot/config.py
            FOUND="$HOST"
            break
        fi
        printf "."
    done
    echo ""

    if [ -z "$FOUND" ]; then
        echo "  ⚠ 隧道地址获取超时，请检查 qqbot-tunnel 服务"
    else
        echo "  隧道就绪: $FOUND"
    fi
fi

echo ""
echo "============================================"
echo "  部署完成！"
echo "  Bot:    systemctl status qqbot"
if [ "$USE_QUICK_TUNNEL" -eq 1 ]; then
    echo "  隧道:   systemctl status qqbot-tunnel"
else
    echo "  图床:   $FIXED_URL"
fi
echo "============================================"
