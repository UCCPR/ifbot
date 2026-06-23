---
name: project-state
description: 幻想收束KOOK Bot完整项目状态：战斗系统、GIF渲染、A卡技能、抽卡系统、KOOK集成
metadata:
  node_type: memory
  type: project
  updated: 2026-06-20
  originSessionId: 58fdfc42-ab8f-40b2-aa92-7682f9a135f6
---

# 幻想收束 KOOK Bot 项目状态

## 项目概述
基于Flask Webhook的KOOK自动抽卡+战斗Bot，支持抽卡、配队、BOSS战、排行榜、战斗GIF动画生成。由QQ版(gacha_bot.py)移植到KOOK版(kook_bot.py)。

## 关键文件
- `qq_bot_ws.py` — QQ WebSocket主程序 (~6,200行)
- `kook_bot.py` — KOOK主程序(Flask Webhook ~4500行)
- `battle_system.py` — 战斗系统(~3900行)
- `gif_renderer.py` — GIF渲染器(~1750行)
- `team_system.py` — 配队系统(队伍图片合成)
- `gacha_bot.py` — 旧QQ版(Napcat ~5500行)
- `config.py` — 配置（含CDKEYS兑换码）
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

### 重要更新 (2026-06-21)
1. **A卡触发条件扩展**: 12→29种，修复`自身`前缀匹配bug（解析用`自身技能时`，调用用`技能时`→不匹配）
2. **一对角色=自身**: `我方一对角色技能时`等6种本质同`自身`版
3. **战斗日志帧补全**: 所有状态变化点(攻击/退场/HP阈值/DoT/SP满/眩晕解除/替补/回合到期/P5b/E类)都有_log帧
4. **状态去重**: _state_hash()计算HP/alive/position/buffs/debuffs哈希，强制帧跳过检查，非强制帧hash不变就只写文本
5. **攻击内A卡逐帧**: 攻击函数返回的每个[A]行产生独立parsable帧

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
- P5 被攻击时(伤害/暴击/技能/必杀) + P5b(敌方动作/自身以外友方触发)
- P6 HP阈值(50%/30%)
- P7 敌方SP满时
- P10 退场时(遗言效果)
- E类 敌方行动结束且一对角色HP<50%

### A卡触发条件 (29种，2026-06-21更新)
**自身类**: 行动开始时, 自身技能时, 自身必杀时, 自身对敌方造成伤害时, 自身对敌方暴击时, 自身受到伤害时, 自身使敌方退场时, 自身退场时, 击破时, 自身从a卡以外被弱体时
**一对角色类(同自身)**: 我方一对角色技能时/必杀时/退场时/受到伤害时/对敌方暴击时/使敌方退场时
**队友类**: 自身以外的我方技能时/必杀时/退场时
**敌方类**: 敌方行动开始时, 敌方技能时, 敌方必杀时, 敌方对我方角色暴击时, 敌方SP满时
**HP/入场**: 替补入场时, HP低于50%时, HP低于30%时
**复合**: 敌方行动结束且我方一对角色HP少于一半时
> 关键规则: `自身`=A卡挂载的B卡, `我方一对角色`=B+A组合体=同`自身`

### 战斗日志帧系统 (2026-06-21)
- 两条并行日志: `battle_log`(文本) + `parsable_battle_log`(结构化，含HP/buff/debuff快照)
- 强制帧(永远记录): round_start, sp_info, turn_switch, attack, enter, swap, battle_end, retreat, hp_threshold
- 非强制帧(状态hash不变就跳过): assist_trigger, trigger, dot_damage, stun_recover, debuff_trigger, buff_expiry
- 每个单位行动: 攻击→P5b→P10→P6→E→弱体，全部跑完后统一_log一次
- 攻击内A卡触发有独立逐帧

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
- 排行榜奖励: `info/ranking_rewards.json` (每日12:00结算前三名呱太+获奖历史)
- CDKEY兑换记录: `info/cdkey_{user_id}.json` (2026-06-20新增)
- 队伍session: `info/team_session_{user_id}.json` (翻页+筛选状态)
- 每日自动备份: `backup/YYYY-MM-DD/`

## QQ机器人 WebSocket 版 (2026-06-18新增, 2026-06-19/20更新)

### 文件统计 (2026-06-22 最终)
| 文件 | 行数 | 说明 |
|------|------|------|
| `qq_bot_ws.py` | ~6,300 | 主程序 (botpy WebSocket, 含排行榜奖励结算/CDKEY/筛选) |
| `kook_bot.py` | 4,496 | KOOK版 (Flask Webhook) |
| `battle_system.py` | ~3,920 | 战斗引擎 (共用, 29种A卡触发条件, P2替补位置修复) |
| `gif_renderer.py` | ~1,860 | GIF渲染 (共用, attack_internal A卡事件文本/retreat帧) |
| `gacha_bot.py` | 5,558 | 旧QQ版 (Napcat) |
| `team_system.py` | 1,350 | 配队系统 (共用, 含颜色/类型筛选) |
| **总计** | **~23,500** | |

### 关键技术
- **botpy WebSocket**: 官方SDK，无需Webhook/HTTPS/签名验证
- **图片发送**: Cloudflare Tunnel → post_group_file(url) → msg_type=7 media；上传后延迟5s删文件
- **GIF缓存**: static_images/gifs/，相同战斗hash复用，每用户保留3个
- **去重方案**: 全部合并文字+图片为单条消息，不加延时
- **GIF优化**: scale=1, optimize=False, quality=30 (~500KB)
- **GIF冷却**: 同用户3分钟
- **Buff图标**: 40+关键词映射到state_icon文件
- **部署**: systemd 服务 + 启动命令.txt
- **排行榜奖励**: 每日12:00结算，前三名真人玩家依次获45000/35000/25000呱太，AI跳过；离线补结算；每天最多一次；个人记录可查获奖历史；祝贺通知跟随触发者（群聊→发群，私聊→发私聊，启动补结算→只记日志不发消息）
- **数据安全**: 全量load→修改特定字段→_atomic_json_save(临时文件+rename)，崩溃不丢数据

### 队伍我的卡筛选 (2026-06-20新增)
- `队伍 我的卡 红/绿/蓝/黄/紫` — 按颜色筛选（含超属性）
- `队伍 我的卡 超红/超绿/...` — 精确匹配超属性（不含普通）
- `队伍 我的卡 B/A` — 按战斗/支援类型筛选
- 组合使用: `队伍 我的卡 红 B`
- xlsx文件用赤/緑/青，底层自动映射为红/绿/蓝
- 筛选状态保持到翻页

### CDKEY兑换系统 (2026-06-20新增)
- `config.py` 配置 `CDKEYS = {"CODE": {"gacha": 呱太, "red_crystal": 红碎片, "blue_crystal": 蓝碎片, "desc": "描述"}}`
- 命令: `兑换 ZMDBOT2026`（大写字母+数字≥4位自动识别）
- 每用户每KEY限一次，记录在 `info/cdkey_{user_id}.json`
- **增量发放**: load→修改特定字段→atomic_save，绝不全量覆盖

### 碎片分色兑换 (2026-06-20改造)
- `兑换红碎片` / `兑换红` — 仅兑红色碎片 (1:5呱太)
- `兑换蓝碎片` / `兑换蓝` — 仅兑蓝色碎片 (1:20呱太)
- `兑换` / `兑换呱太` — 兑全部碎片（原有行为不变）
- handle_exchange_crystal 增加 crystal_type 参数

### 已实现命令
签到、获取呱太、十连/单抽、限定十连、战斗(含VS图)、挑战(含排名/含@玩家)、BOSS战(含VS图)、战斗日志/GIF(分离+缓存)、配队(我的卡/筛选/设置/切换/预设/自动/防守队)、排行榜(挑战格式/每日前三奖励)、抽卡排行、兑换呱太/兑换红碎片/兑换蓝碎片、CDKEY兑换、三王女、三星池(红抽/蓝抽)、个人记录(含排行榜获奖历史)、昵称、数据迁移(/绑定)、管理员命令(全榜替)、gif列表
