#!/bin/bash
# QQ机器人一键启动脚本
# 自动: 启动图片HTTP服务 → Cloudflare隧道 → 更新config → 启动Bot

set -e
cd "$(dirname "$0")"
IMAGE_PORT=18080
CONFIG_FILE="config.py"
PID_FILE="/tmp/qq_bot_ws.pid"

echo "============================================"
echo "  QQ机器人 一键启动"
echo "============================================"

# 1. 停止旧进程
echo "[1/4] 停止旧进程..."
if [ -f "$PID_FILE" ]; then
    old_pid=$(cat "$PID_FILE")
    kill "$old_pid" 2>/dev/null && echo "  已停止旧Bot PID=$old_pid" || true
    rm "$PID_FILE"
fi
pkill -f "cloudflared.*$IMAGE_PORT" 2>/dev/null && echo "  已停止旧隧道" || true
pkill -f "qq_bot_ws.py" 2>/dev/null || true
sleep 1

# 2. 创建静态图片目录
mkdir -p static_images

# 3. 启动Python内置图片HTTP服务（后台）
echo "[2/4] 启动图片HTTP服务 (端口 $IMAGE_PORT)..."
python3 -c "
import http.server, os, threading
os.chdir('static_images')
h = http.server.HTTPServer(('0.0.0.0', $IMAGE_PORT), http.server.SimpleHTTPRequestHandler)
t = threading.Thread(target=h.serve_forever, daemon=True)
t.start()
# 保持进程存活，让 cloudflared 能连接
import time
while True: time.sleep(60)
" &
IMG_PID=$!
echo "  图片服务 PID=$IMG_PID"

# 4. 启动Cloudflare Tunnel（后台），自动获取URL
echo "[3/4] 启动 Cloudflare Tunnel..."
cloudflared tunnel --url "http://localhost:$IMAGE_PORT" \
    --no-autoupdate 2>&1 | while read line; do
    echo "  [cloudflared] $line"
    # 检测trycloudflare地址
    if echo "$line" | grep -q "trycloudflare.com"; then
        HOST=$(echo "$line" | grep -oP 'https://\K[^/]+\.trycloudflare\.com' | head -1)
        if [ -n "$HOST" ]; then
            echo ""
            echo "  >>> 隧道地址: https://$HOST"
            # 更新config.py
            if grep -q "IMAGE_HOST" "$CONFIG_FILE"; then
                sed -i "s/IMAGE_HOST = \".*\"/IMAGE_HOST = \"$HOST\"/" "$CONFIG_FILE"
            else
                echo "IMAGE_HOST = \"$HOST\"" >> "$CONFIG_FILE"
            fi
            echo "  >>> 已更新 $CONFIG_FILE"
            break
        fi
    fi
done &
TUNNEL_PID=$!

# 等待隧道就绪
echo "  等待隧道就绪..."
for i in $(seq 1 30); do
    if grep -q "IMAGE_HOST = \"" "$CONFIG_FILE" 2>/dev/null; then
        HOST=$(grep "IMAGE_HOST" "$CONFIG_FILE" | grep -oP '".*?"' | tr -d '"')
        if [ -n "$HOST" ] && [ "$HOST" != "" ]; then
            echo "  隧道已就绪: $HOST"
            break
        fi
    fi
    sleep 2
done

# 5. 启动Bot主程序（前台）
echo "[4/4] 启动 Bot..."
python3 qq_bot_ws.py &
BOT_PID=$!
echo "$BOT_PID" > "$PID_FILE"
echo "  Bot PID=$BOT_PID"

echo ""
echo "============================================"
echo "  启动完成！"
echo "  Bot PID: $BOT_PID"
echo "  查看日志: tail -f nohup.out"
echo "  停止: bash stop_qq_bot.sh"
echo "============================================"

# 等待Bot进程
wait $BOT_PID
