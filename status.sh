#!/bin/bash
# QQ Bot 状态检查 - 查看运行中的进程
echo "============================================"
echo "  QQ Bot 进程状态"
echo "============================================"

# 1. PID 锁
if [ -f /tmp/qq_bot_ws.pid ]; then
    PID=$(cat /tmp/qq_bot_ws.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "  PID 锁: ✓ $PID (运行中)"
    else
        echo "  PID 锁: ✗ $PID (进程已死，残留文件)"
    fi
else
    echo "  PID 锁: 无"
fi

# 2. Bot 进程
echo ""
echo "  Bot 进程:"
BOT_COUNT=$(ps aux 2>/dev/null | grep -c '[q]q_bot_ws.py' || echo 0)
if [ "$BOT_COUNT" -eq 1 ]; then
    ps aux | grep '[q]q_bot_ws.py' | awk '{printf "    PID=%s CPU=%s%% MEM=%s%% 运行时间=%s\n", $2, $3, $4, $10}'
elif [ "$BOT_COUNT" -gt 1 ]; then
    echo "    ⚠ 发现 $BOT_COUNT 个进程！"
    ps aux | grep '[q]q_bot_ws.py' | awk '{printf "    PID=%s CPU=%s%% MEM=%s%% 运行时间=%s\n", $2, $3, $4, $10}'
else
    echo "    未运行"
fi

# 3. 端口 18080
echo ""
echo "  端口 18080:"
PORT_PID=$(fuser 18080/tcp 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    PORT_CMD=$(ps -p "$PORT_PID" -o comm= 2>/dev/null || echo "?")
    echo "    PID=$PORT_PID ($PORT_CMD)"
else
    echo "    未监听 ⚠"
fi

# 4. Cloudflare 隧道
echo ""
echo "  Cloudflare 隧道:"
TUNNEL_COUNT=$(ps aux 2>/dev/null | grep -c '[c]loudflared.*18080' || echo 0)
if [ "$TUNNEL_COUNT" -gt 0 ]; then
    ps aux | grep '[c]loudflared.*18080' | awk '{printf "    PID=%s 运行时间=%s\n", $2, $10}'
    # 提取隧道地址
    journalctl -u qqbot-tunnel.service --no-pager -n 30 2>/dev/null | grep -o 'https://[^ ]*\.trycloudflare\.com' | tail -1 | awk '{print "    URL:", $1}'
else
    echo "    未运行 ⚠"
fi

# 5. systemd 服务
echo ""
echo "  systemd 服务:"
for svc in qqbot qqbot-tunnel qqbot-image; do
    if systemctl is-enabled "$svc" 2>/dev/null | grep -q enabled; then
        STATE=$(systemctl is-active "$svc" 2>/dev/null)
        case "$STATE" in
            active)   ICON="✓" ;;
            inactive) ICON="✗" ;;
            failed)   ICON="✗✗" ;;
            *)        ICON="? ($STATE)" ;;
        esac
        echo "    $ICON $svc"
    fi
done
if systemctl is-enabled qqbot-image 2>/dev/null | grep -q enabled; then
    echo "    ⚠ qqbot-image 应删除！运行: systemctl disable --now qqbot-image"
fi

echo ""
echo "============================================"
echo "  正常标准: 1个Bot进程 + 1个Tunnel进程"
echo "  异常时: pkill -f qq_bot_ws.py && bash start_qq_bot.sh"
echo "============================================"
