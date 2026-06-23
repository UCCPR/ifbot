#!/bin/bash
# 手动启动隧道守护 — 崩了自动重启
# 用法: nohup bash keep_tunnel.sh > /tmp/qqbot_tunnel.log 2>&1 &
# 停止: pkill -f keep_tunnel.sh

while true; do
    cloudflared tunnel --url http://localhost:18080 --no-autoupdate
    sleep 5
done
