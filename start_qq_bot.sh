#!/bin/bash
# QQ机器人一键启动脚本
# 图片HTTP服务由 qq_bot_ws.py 内置启动，无需单独启动

set -e
cd "$(dirname "$0")"
IMAGE_PORT=18080
CONFIG_FILE="config.py"
PID_FILE="/tmp/qq_bot_ws.pid"
# 从 config.py 解析 IMAGE_HOST（grep 解析，不依赖 python3 环境，与 Bot 运行时 _get_image_base_url 一致）
CONFIGURED_HOST=""
if [ -f "$CONFIG_FILE" ]; then
    while IFS= read -r line; do
        if [[ "$line" =~ ^[[:space:]]*IMAGE_HOST[[:space:]]*=[[:space:]]*[\"\']([^\"\']*)[\"\'] ]]; then
            CONFIGURED_HOST="${BASH_REMATCH[1]}"
            break
        fi
    done < "$CONFIG_FILE"
fi
USE_QUICK_TUNNEL=1
case "$CONFIGURED_HOST" in
    ""|localhost*|*.trycloudflare.com) ;;
    *) USE_QUICK_TUNNEL=0 ;;
esac

echo "============================================"
echo "  QQ机器人 一键启动"
echo "============================================"

# 1. 停止旧进程
echo "[1/3] 停止旧进程..."
if [ -f "$PID_FILE" ]; then
    old_pid=$(cat "$PID_FILE")
    kill "$old_pid" 2>/dev/null && echo "  已停止旧Bot PID=$old_pid" || true
    rm "$PID_FILE"
fi
if [ "$USE_QUICK_TUNNEL" -eq 1 ]; then
    pkill -f "cloudflared.*$IMAGE_PORT" 2>/dev/null && echo "  已停止旧临时隧道" || true
fi
pkill -f "qq_bot_ws.py" 2>/dev/null || true
sleep 1

# 2. 创建静态图片目录
mkdir -p static_images

# 3. 先启动Bot（后台，内置图片HTTP服务 + PID文件锁），再启动Cloudflare Tunnel
echo "[2/3] 启动 Bot（含内置图片服务 :$IMAGE_PORT）..."
python3 qq_bot_ws.py > /tmp/qq_bot_ws.log 2>&1 &
BOT_PID=$!
sleep 2
# 检测 Bot 是否启动成功（PID 锁是否获取成功）
if ! kill -0 "$BOT_PID" 2>/dev/null; then
    echo "  ✗ Bot 启动失败！可能已有实例在运行。"
    echo "  查看日志: tail -20 /tmp/qq_bot_ws.log"
    echo "  强制重启: bash stop_qq_bot.sh && bash start_qq_bot.sh"
    exit 1
fi
echo "  Bot PID=$BOT_PID"

# 4. 固定图床优先；仅在没有固定域名时创建 Quick Tunnel。
if [ "$USE_QUICK_TUNNEL" -eq 0 ]; then
    echo "[3/3] 使用固定图片域名: $CONFIGURED_HOST"
    HOST="$CONFIGURED_HOST"
    FIXED_URL="$HOST"
    case "$FIXED_URL" in http://*|https://*) ;; *) FIXED_URL="https://$FIXED_URL" ;; esac
    if curl -fsSI --max-time 10 "$FIXED_URL/" >/dev/null 2>&1; then
        echo "  固定图床连通正常"
    else
        echo "  ⚠ 固定图床当前无法访问，请检查 named tunnel/反向代理是否指向 localhost:$IMAGE_PORT"
    fi
else
    echo "[3/3] 启动临时 Cloudflare Tunnel..."
    cloudflared tunnel --url "http://localhost:$IMAGE_PORT" \
        --no-autoupdate > /tmp/qq_bot_tunnel.log 2>&1 &

    echo "  等待隧道就绪..."
    HOST=""
    for i in $(seq 1 30); do
        HOST=$(grep -oP 'https://\K[^ ]+\.trycloudflare\.com' /tmp/qq_bot_tunnel.log 2>/dev/null | head -1)
        if [ -n "$HOST" ]; then
            echo "  >>> 临时隧道地址: https://$HOST"
            if grep -q "IMAGE_HOST" "$CONFIG_FILE"; then
                sed -i "s|^[[:space:]]*IMAGE_HOST = [\"'].*|IMAGE_HOST = \"$HOST\"|" "$CONFIG_FILE"
            else
                echo "IMAGE_HOST = \"$HOST\"" >> "$CONFIG_FILE"
            fi
            break
        fi
        sleep 2
    done

    if [ -z "$HOST" ]; then
        echo "  ⚠ 隧道启动超时，请手动检查 /tmp/qq_bot_tunnel.log"
    fi
fi

echo ""
echo "============================================"
echo "  启动完成！"
echo "  Bot PID: $BOT_PID"
echo "  Bot日志: tail -f /tmp/qq_bot_ws.log"
if [ "$USE_QUICK_TUNNEL" -eq 1 ]; then
    echo "  隧道日志: tail -f /tmp/qq_bot_tunnel.log"
else
    echo "  图片域名: $FIXED_URL"
fi
echo "  停止: bash stop_qq_bot.sh"
echo "============================================"

# 等待Bot进程
wait $BOT_PID
