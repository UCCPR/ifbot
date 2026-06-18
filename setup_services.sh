#!/bin/bash
# QQ Bot 服务器部署脚本 - 安装为系统服务（24/7运行）
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

# 1. 安装系统服务
echo "[1/3] 安装 systemd 服务..."
cp qqbot-image.service /etc/systemd/system/
cp qqbot-tunnel.service /etc/systemd/system/
cp qqbot.service /etc/systemd/system/
systemctl daemon-reload

# 2. 启动图片服务和隧道
echo "[2/3] 启动基础服务..."
systemctl enable --now qqbot-image.service
systemctl enable --now qqbot-tunnel.service
sleep 3

# 3. 等待Cloudflare隧道就绪，获取地址
echo "[3/3] 获取隧道地址..."
for i in $(seq 1 30); do
    # 从cloudflared日志获取URL
    URL=$(journalctl -u qqbot-tunnel.service --no-pager -n 20 2>/dev/null | grep -oP 'https://\K[^ ]+\.trycloudflare\.com' | head -1)
    if [ -n "$URL" ]; then
        echo "  隧道地址: https://$URL"
        # 更新config.py
        if grep -q "IMAGE_HOST" config.py; then
            sed -i "s/IMAGE_HOST = \".*\"/IMAGE_HOST = \"$URL\"/" config.py
        else
            echo "IMAGE_HOST = \"$URL\"" >> config.py
        fi
        echo "  已更新 config.py"
        break
    fi
    sleep 3
done

# 4. 启动Bot
echo "启动 Bot..."
systemctl enable --now qqbot.service

echo ""
echo "============================================"
echo "  部署完成！"
echo ""
echo "  常用命令:"
echo "    查看Bot状态:  systemctl status qqbot"
echo "    查看Bot日志:  journalctl -u qqbot -f"
echo "    查看隧道日志: journalctl -u qqbot-tunnel -f"
echo "    重启Bot:      systemctl restart qqbot"
echo "    停止Bot:      systemctl stop qqbot"
echo "    隧道新地址:   journalctl -u qqbot-tunnel -n 5 | grep trycloudflare"
echo "============================================"
