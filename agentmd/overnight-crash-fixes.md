---
name: overnight-crash-fixes
description: 2026-06-19 QQ Bot 全面稳定化：17项修复覆盖崩溃、数据损坏、重复消息、双进程、隧道时序
metadata: 
  node_type: memory
  type: project
  updated: 2026-06-19
  originSessionId: abe1d3ea-24c2-4f57-9c1d-d48db61ff9a5
---

# QQ Bot 稳定化修复全集 (2026-06-19)

## 第一轮：过夜宕机修复 (P0)

### 1. `_route()` 零异常保护
**问题**: 消息路由无 try/except，任何 handler 异常直接炸穿 botpy → Bot 崩溃。
**修复**: 提取 `_route_impl()`，外层 `_route()` 包裹 `try/except`，异常写 traceback 日志，Bot 不中断。

### 2. 端口 18080 冲突
**问题**: systemd `qqbot-image.service` 和 Bot 内置 `_start_image_server()` 同时抢 18080。
**修复**: 删除 `qqbot-image.service`，`_start_image_server()` 加 `SO_REUSEADDR` + 异常捕获。

### 3. systemd 级联斩杀
**问题**: `qqbot.service` 用 `Requires=qqbot-tunnel.service`，隧道断线 → systemd 杀 Bot。
**修复**: `Requires=` → `Wants=`。去掉 `Restart=always`（用户要求）。隧道独立于 Bot。

### 4. `requests.post` 同步阻塞事件循环
**问题**: 死代码 `_upload_file()` 用同步 `requests.post`，如果被调用会阻塞 WebSocket 心跳。
**修复**: 删除 `_upload_file()` + `import requests`。

### 5. `MESSAGE_COUNTER` 内存泄漏
**问题**: 速率限制字典只增不删。
**修复**: 每 100 条消息清理超过 2 分钟的过期条目。

### 6. `static_images/` 临时文件堆积
**问题**: 图片发送失败时文件残留，长期占满磁盘。
**修复**: `_cleanup_temp_images()` 启动时 + atexit 清理超过 10 分钟的 `bot_*.png`。

---

## 第二轮：消息重复 & 数据损坏 (P0)

### 7. `return jsonify(...)` → 双重发送
**问题**: 所有 handler 同时 `send_message()` + `return jsonify({...})`，旧 `jsonify()` 返回真实 dict，botpy 当作被动回复再次发送 → 每条命令两条消息。
**修复**: `jsonify()` 永远返回 `None`。80+ 处调用点无需改动。

### 8. JSON 文件非原子写入 → 崩溃丢数据
**问题**: `save_pity_data` 等直接用 `open("w")` 写入，崩溃时文件写一半 → 下次加载 `JSONDecodeError` → 返回空默认数据 → **用户呱太/抽卡记录全部归零**。
**修复**: 新增 `_atomic_json_save()` (写临时文件 → `os.replace` 原子替换)。全部 10 个 save 点改为原子写入。

### 9. msg_seq 去重错误
**问题**: `handle_gacha` 同时发主动消息 + `return jsonify(...)` 被动回复 → 同一 `msg_id` 两次回复 → QQ 去重拦截 → `消息被去重，请检查请求msgseq`。
**修复**: 同 #7，`jsonify` 返回 `None`。另加 msg_seq 碰撞重试（sleep 0.5s 换时间戳，最多 3 次）。

---

## 第三轮：双进程 & 隧道时序 (P0)

### 10. PID 文件锁防双开
**问题**: 用户容易忽略后台进程，启动第二个 Bot 实例 → 两个进程同时回复同一条消息 → msg_seq 冲突。
**修复**: 启动时 `fcntl.flock(LOCK_EX|LOCK_NB)` 文件锁，第二个进程检测到锁 → 报错退出。支持 Linux/macOS/Windows。

### 11. `setup_services.sh` 时序修复 (反复修补)
**问题**: 脚本经历了多次迭代：
- 初版：`qqbot-image.service` + `qqbot-tunnel.service` + `qqbot.service` 三服务，但端口冲突
- 第二版：删 qqbot-image，临时 HTTP 占端口取 URL → kill → 重启 Bot → 隧道 URL 过期不匹配
- 第三版：Bot 先启 → 隧道后启 → Bot 重启加载 IMAGE_HOST → 隧道 530
- **最终版**：Bot 先启(占 18080) → 隧道后启(连上 Bot HTTP) → `journalctl --since` 获取本次 URL → 更新 config.py → Bot 动态读取无需重启
**最终流程**:
```bash
[1/3] 清理旧服务 + 释放 18080 + 禁用旧 qqbot-image
[2/3] 启动 Bot (HTTP 服务占 18080)
[3/3] stop → start 隧道 → --since 限时获取 URL → 更新 config.py
```
**关键点**: `systemctl stop` 再 `start`(不用 restart)、`journalctl --since "1分钟前"` 避免旧 URL、`grep -oE` 兼容所有 grep、Bot 动态读 IMAGE_HOST 无需重启。

### 12. Bot 动态读取 IMAGE_HOST
**问题**: 旧代码启动时缓存 `IMAGE_HOST`，更新 config.py 后必须重启 Bot → 重启时 HTTP 服务断开 → 隧道 530。
**修复**: `_upload_and_send_image()` 每次发图实时从 `config.py` 文件读取 `IMAGE_HOST`。手动改 config.py 或脚本更新后立即生效，Bot 无需重启。

---

## 第四轮：功能修复

### 13. 盲盒会话可取消/可覆盖
**问题**: 用户抽了盲盒没开 → 所有后续命令被拦截 → 只能开完或等过期。
**修复**: `取消`/`不要了`/`放弃` 清会话；`十连`/`单抽`/`限定十连` 自动清旧会话抽新的。

### 14. @玩家 挑战
**问题**: `挑战` 只支持排名数字，不能直接 @ 玩家。
**修复**: 新增 `challenge_player()` 函数，`@Bot 挑战 @某人` 查排行找排名 → 走 `challenge_rank` 流程。

---

## 第五轮：GIF 渲染修复

### 15. Buff 图标映射统一
**问题**: `gif_renderer.py` 和 `battle_system.py` 各自维护一套 icon_map，11 个映射不一致。
**修复**: gif_renderer 改为 `from battle_system import BUFF_ICON_MAP`，单一数据源。修正 11 个错误 + 补 3 个缺失。

### 16. 攻击方向箭头反转
**问题**: 玩家方箭头朝下、敌方朝上 → 视觉反了。
**修复**: `arrow_map_p` 和 `arrow_map_e` 交换（只改卡片渲染箭头，不动角色名约定）。

### 17. 战斗位置冲突
**问题**: 角色阵亡后 `position` 不清空，替补继承同位置 → 同位置堆积多个死单位 → GIF 渲染错乱。
**修复**: P2 替补上场后，所有死单位 `position = -1`。

---

## 文件变更总览

| 文件 | 变更 |
|------|------|
| `qq_bot_ws.py` | _route 异常保护、jsonify→None、原子写、PID锁、动态 IMAGE_HOST、盒子取消、@挑战、msg_seq 重试、SO_REUSEADDR、速率清理、临时文件清理、删 requests/_upload_file |
| `qqbot.service` | Requires→Wants、注释掉 Restart |
| `qqbot-tunnel.service` | 移除 qqbot-image 依赖、注释掉 Restart |
| `qqbot-image.service` | **删除** |
| `gif_renderer.py` | 导入 BUFF_ICON_MAP、箭头方向交换 |
| `battle_system.py` | P2 后清死单位 position |
| `setup_services.sh` | **重写**: stop→start 隧道、--since 限时取 URL、无重启 |
| `start_qq_bot.sh` | 移除独立图片服务、PID 检测 |
| `stop_qq_bot.sh` | PID 文件精准 kill |
| `status.sh` | **新增**: 一键进程/端口/隧道/服务检查 |
| `启动命令.txt` | 更新管理员命令、status.sh、服务架构 |
