---
name: project-state
description: 幻想收束KOOK Bot完整项目状态 - 战斗系统、GIF渲染、A卡技能、抽卡系统
metadata: 
  node_type: memory
  type: project
  updated: 2026-06-18
  originSessionId: 58fdfc42-ab8f-40b2-aa92-7682f9a135f6
---

# 幻想收束 KOOK Bot 项目状态

## 项目概述
基于Flask Webhook的KOOK自动抽卡+战斗Bot，支持抽卡、配队、BOSS战、排行榜、战斗GIF动画生成。由QQ版(gacha_bot.py)移植到KOOK版(kook_bot.py)。

## 关键文件
- `kook_bot.py` — KOOK主程序(Flask Webhook ~4500行)
- `battle_system.py` — 战斗系统(~3600行)
- `gif_renderer.py` — GIF渲染器(~1750行)
- `team_system.py` — 配队系统(队伍图片合成)
- `卡牌信息.xlsx` — 抽卡池数据(1/2/3星)
- `cards_completed.xlsx` — 战斗数值(3星详细数据)
- `state_icon/` — 76个状态图标
- `iconimage/` — 角色立绘
- `level/` — 星级框/标签/背景图

## GIF渲染系统 (gif_renderer.py)

### 渲染流程
1. `battle_to_gif_bytes(result)` — 主入口，返回BytesIO
2. `_parse_parsable_log()` — 优先解析结构化parsable_log
3. `_parse_battle_log()` — 回退解析文本log
4. `_calculate_hp_changes()` — 计算每帧HP变化量和攻击方向
5. `_render_team_section()` ×2 — 渲染敌我双方5列战场
6. `_render_character_card()` — 渲染单张角色卡(立绘+框+阵亡覆盖)
7. 编译GIF → BytesIO → KOOK asset API上传 → 卡片消息发送

### 战场布局(5列)
- 位置0: ↙/↖, 位置1: ←/←, 位置2: ↓/↑, 位置3: →/→, 位置4: ↘/↗
- 初始上场3人占位置0/2/4，位置1/3空位用于换位
- 替补队列: position=-1

### GIF帧布局(缩放前480×~590px, 后×2=960×~1180)
```
[事件描述]                   30px
[敌方队伍区域]               216px (5列卡+HP条+buff图标+攻击方向)
[Round X - Turn]             22px
[P-SP: ████░░ 240/300]      10px (蓝色)
[E-SP: ████░░ 180/300]      10px (红色)
[玩家队伍区域]               216px
```

### 已实现功能
- 5列角色卡渲染(立绘裁剪+内框+外框)
- HP条(绿>50%/黄>25%/红≤25%) + 数值文字
- HP变化显示(红框=伤害,绿框=回复,带[普/技/终/A]标签)
- BUFF/DEBUFF图标(从state_icon/自动匹配)
- 攻击方向箭头(攻击者→目标)
- 阵亡状态(红色覆盖+X标记)
- 特殊效果文字(盾抵挡/反射/回避/不屈/减伤)
- SP条实时更新(玩家蓝/敌方红)
- 事件描述文字(换位/替补上场/A卡效果)
- 胜利画面(Player WIN!/Enemy WIN!/Draw!)
- 帧计数器([N/total])
- 替补上场(清空buffs/debuffs)
- 阵亡清场(攻击帧后position=-1)

### 重要修复 (2026-06-18)
1. **攻击帧HP同步**: attack handler读取parsable_log的player_positions/enemy_positions更新HP
2. **特殊效果可视化**: 读取hit_status字段显示盾抵挡/反射/回避/不屈
3. **初始帧清空BUFF**: 战斗开始帧清除A卡预触发产生的buffs/debuffs
4. **战斗结束败方全灭**: battle_end标记败方所有单位alive=False/hp=0
5. **阵亡清场+替补替换**: 攻击帧后死单位position=-1, enter事件替补上场清buffs/debuffs
6. **SP条实时显示**: 从sp_info事件读取SP值，渲染双方SP条

### hit_status系统(battle_system.py补充)
- `get_hit_status()`支持: 回避/抵挡/反射/吸收/减伤/不屈
- `execute_normal_attack()`：回避/不屈写入_last_damage_info
- `execute_skill_attack()`：全部5种效果写入_last_damage_info
- `execute_ultimate_attack()`：全部5种效果写入_last_damage_info

## 战斗系统 (battle_system.py)
### 战场配置
- 5列战场，初始部署3人占0/2/4列，替补5+位置
- SP上限300，必杀消耗100，技能消耗30
- B+A合并为一个角色（A卡属性合并到B卡）
- 同色加成1.05，属性克制1.5/0.6，超属性×1.2

### 优先级流程
- P1 开场被动(仅上场3人，位置[0,2,4])
- P2 替补入场(继承阵亡位置)
- P3 行动开始时/敌方行动开始时
- P4 攻击决策+执行(按速度排序: 必杀>技能>普攻)
- P5 被攻击时(伤害/暴击/技能/必杀)
- P6 HP阈值(50%/30%)
- P7 敌方SP满时
- P10 退场时(遗言效果)

## KOOK集成
### 图片/GIF发送
1. `upload_kook_image(image)` → POST `/api/v3/asset/create` → 返回URL
2. `send_kook_card_message()` → type:10卡片消息, 内嵌image模块
3. `send_kook_gif_bytes()` — BytesIO GIF上传+卡片消息发送

### GIF触发命令
- `/战斗` / `/对战` — AI对战，自动生成GIF
- `/挑战 <排名>` — 排行榜挑战，自动生成GIF
- `/BOSS战` — BOSS战，自动生成GIF
- `/战斗GIF` / `/战斗日志` — 查看最近战斗GIF回放

## 数据存储
- 抽卡记录: `info/pity_{user_id}.json`
- 呱太数据: `info/gacha_{user_id}.json`
- 签到数据: `info/signin_{user_id}.json`
- 队伍配置: `info/team_{user_id}.json`
- 战斗记录: `info/battle_{user_id}.json` (滚动保留3次)
- 排行榜: `info/ranking.json`
- 每日自动备份: `backup/YYYY-MM-DD/`

## QQ机器人 WebSocket 版 (2026-06-18新增)

### 架构
- `qq_bot_ws.py` — 主程序（botpy WebSocket，约5600行）
- 复用 `battle_system.py` / `gif_renderer.py` / `team_system.py`
- 旧版 `gacha_bot.py` (Napcat) 和 `kook_bot.py` (KOOK) 保留

### 关键技术
- **botpy WebSocket**: 官方SDK，无需Webhook/HTTPS/签名验证
- **图片发送**: Cloudflare Tunnel → post_group_file(url) → msg_type=7 media
- **用户标识**: openid（十六进制），QQ号不再暴露
- **被动回复**: msg_id参数，5分钟有效
- **去重方案**: 合并文字+图片为单条消息
- **部署**: systemd 守护进程，崩溃自动重启

### 已实现命令
签到、获取呱太、十连/单抽、限定十连、战斗、挑战、BOSS战、战斗日志/GIF、配队(我的卡/设置/切换/预设/自动)、排行榜、抽卡排行、兑换呱太、三王女、三星池(红抽/蓝抽)、个人记录、昵称、数据迁移(/绑定)、管理员命令、全榜替

### 用户偏好(新增)
- QQ群聊用botpy WebSocket，KOOK用Flask Webhook
- 图片用Cloudflare Tunnel，不依赖外部图床
- 用户数据用openid存储，支持QQ号绑定迁移
- 合并文字图片防去重，不添加msg_seq
