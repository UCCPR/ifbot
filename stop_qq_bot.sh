#!/bin/bash
echo "停止 QQ Bot..."
PID_FILE="/tmp/qq_bot_ws.pid"
if [ -f "$PID_FILE" ]; then
    kill $(cat "$PID_FILE") 2>/dev/null && echo "已停止 Bot" || true
    rm "$PID_FILE"
fi
pkill -f "cloudflared.*18080" 2>/dev/null && echo "已停止隧道" || true
pkill -f "qq_bot_ws.py" 2>/dev/null || true
echo "完成"
