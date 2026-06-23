#!/bin/bash
echo "停止 QQ Bot..."
PID_FILE="/tmp/qq_bot_ws.pid"

# 1. 先尝试优雅停止（通过 PID 文件）
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill "$PID" 2>/dev/null; then
        echo "  已停止 Bot (PID=$PID)"
        rm -f "$PID_FILE"
    else
        echo "  PID=$PID 进程已不存在，清理锁文件"
        rm -f "$PID_FILE"
    fi
fi

# 2. 兜底：kill 所有残留进程
pkill -f "cloudflared.*18080" 2>/dev/null && echo "  已停止隧道" || true
pkill -f "qq_bot_ws.py" 2>/dev/null && echo "  已停止残留 Bot 进程" || true

rm -f "$PID_FILE"
echo "完成"
