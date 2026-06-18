---
name: qq-bot-ws-guide
description: "QQ机器人WebSocket版部署和配置指南 - botpy官方SDK, 群聊被动回复, Cloudflare图片隧道"
metadata: 
  node_type: memory
  type: project
  updated: 2026-06-18
  originSessionId: 12f42f19-cfa8-401b-89eb-57c759d2da8e
---

# QQ机器人 WebSocket 版部署指南

## 架构
- `qq_bot_ws.py` — QQ机器人主程序（botpy WebSocket，无需Webhook/Flask）
- `battle_system.py` / `gif_renderer.py` / `team_system.py` — 共用战斗/GIF/配队系统
- `kook_bot.py` — KOOK版（Webhook，独立运行）

## 启动方式
**两个终端：**

终端1 - Bot主程序:
```bash
cd ~/zmdbot
python3 qq_bot_ws.py
```

终端2 - 图片隧道:
```bash
cloudflared tunnel --url http://localhost:18080
```
拿到 `https://xxx.trycloudflare.com` 后更新 `config.py` 的 `IMAGE_HOST`，重启Bot。

**一键启动:** 运行 `start_qq_bot.sh`

**24/7生产环境部署（systemd守护进程）:**
```bash
cd ~/zmdbot
chmod +x *.sh
sudo bash setup_services.sh
```
安装后Bot崩溃自动重启。管理命令:
```bash
systemctl status qqbot          # 查看状态
journalctl -u qqbot -f          # 查看日志
systemctl restart qqbot         # 重启
```
隧道地址变化时: `journalctl -u qqbot-tunnel -n 5 | grep trycloudflare` 获取新地址，更新 `config.py` 的 `IMAGE_HOST`，`systemctl restart qqbot`

## config.py 配置
```python
QQ_BOT_APP_ID = "1903631383"       # 机器人 AppID
QQ_BOT_SECRET = "xxx"              # 机器人 Secret
QQ_BOT_TOKEN = "xxx"               # 机器人 Token（文件上传用）
ADMIN_QQ = "B9A2B648C9..."         # 管理员 openid
IMAGE_HOST = "xxx.trycloudflare.com"  # Cloudflare Tunnel 地址
```

## 关键技术决策
- **botpy WebSocket**: 用官方SDK，不需要Webhook验证签名
- **Cloudflare Tunnel**: QQ国内服务器访问海外服务器图片的唯一可靠方案
- **被动回复**: 必须带 `msg_id` 参数，5分钟有效期内回复
- **msg_type=7**: 发送富媒体图片时必须用7（不是0文本）
- **msg_seq**: 用毫秒时间戳防去重
- **用户ID**: 使用 openid（十六进制），不再暴露QQ号
- **数据迁移**: 用户发 `/绑定 QQ号` 覆盖迁移旧数据

## 已实现功能
签到、抽卡(含图)、战斗(含GIF)、BOSS战、配队、排行榜、昵称、数据迁移

## 已实现命令
签到、获取呱太、十连/单抽、限定十连、战斗、挑战、BOSS战、战斗日志/GIF、配队(我的卡/设置/切换/预设/自动)、排行榜、抽卡排行、兑换呱太、三王女、三星池(红抽/蓝抽)、个人记录、昵称、数据迁移(/绑定)、管理员命令、全榜替(管理员)

## 已知限制 & 迁移记录
- 图片需Cloudflare Tunnel（海外服务器QQ无法直连）
- 图片方案演进: 公网IP超时 → SM.MS/ImgBB失败 → Cloudflare Tunnel ✅
- 消息去重: 合并文字+图片为单条，不随消息增量发送
- 用户ID: openid替代QQ号，/绑定迁移旧数据
- 管理命令正则: \d+改为[A-F0-9]+匹配hex openid
- 24/7: systemd守护进程，崩溃自动重启
