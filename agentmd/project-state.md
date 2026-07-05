---
name: project-state
description: 幻想收束KOOK/QQ Bot完整项目状态：战斗系统、GIF渲染、A卡技能、抽卡系统、KOOK/QQ集成、代码重构记录
metadata:
  node_type: memory
  type: project
  updated: 2026-07-03
  originSessionId: 58fdfc42-ab8f-40b2-aa92-7682f9a135f6
---

# 幻想收束 KOOK/QQ Bot 项目状态

## 项目概述
基于 botpy WebSocket (QQ) + Flask Webhook (KOOK) 的双平台自动抽卡+战斗 Bot。
支持抽卡、配队、BOSS战、排行榜、战斗GIF动画生成。

## 关键文件 (2026-07-02 全面修复后)

| 文件 | 行数 | 说明 |
|------|------|------|
| `qq_bot_ws.py` | 4,390 | QQ WebSocket 主程序 (botpy, QQBotClient + 核心handler) |
| `battle_system.py` | ~3,250 | 战斗引擎 (共用: 攻击合并/_execute_attack_core, start_battle去重) |
| `gif_renderer.py` | ~1,700 | GIF 渲染 (共用: 入口合并/_render_frames_from_result, RGBA半透明, hp_threshold/trigger帧) |
| `team_system.py` | 1,280 | 配队系统 (共用: auto_build_team拆分为_score/_generate/_allocate) |
| `ranking.py` | 1,191 | 排行榜+挑战+每日结算 (从qq_bot_ws拆分, lazy _qq()导入) |
| `box_system.py` | 487 | 盲盒开箱全流程 (从qq_bot_ws拆分, lazy _qq()导入) |
| `card_image.py` | 249 | 卡牌图片合成 (get_level_image/composite_card等, 中日文属性映射) |
| `gacha_bot.py` | 5,099 | 旧QQ版 (Napcat, 维护模式, 同样应用了图片导入去重) |
| `kook_bot.py` | ~4,500 | KOOK 主程序 (Flask Webhook, 含_atomic_json_save原子写入, rank_adjustment排名交换) |
| `qq_bot.py` | 5,646 | 旧QQ版 (已废弃) |
| **主力7文件合计** | **~13,200** | |

数据文件: `卡牌信息.xlsx` (抽卡池), `cards_completed.xlsx` (战斗数值), `state_icon/` (76图标), `iconimage/`, `level/`

## 2026-07-02 全面修复 (22项, 全部运行时验证通过)

详见 [battle-system-comprehensive-fixes.md](battle-system-comprehensive-fixes.md)

### battle_system.py (10项)
- 除零保护、替补位置溢出、player_on_field过滤、死亡位置备份(_last_valid_position)、P7 SP检查(defender_sp参数)、一对角色排序、箭头重复删除、_state_hash增强(is_broken)

### gif_renderer.py (9项)
- assist事件HP同步、阵亡过渡修复、hp_threshold handler新增、trigger handler新增、retreat同步、SP_BAR_HEIGHT修正(28→24)、RGBA半透明、macOS字体(Darwin)、17处bare except修复

### qq_bot_ws.py (5项)
- BOSS None保护、result安全访问、BOSS冷却泄漏清理、VS图清理、盲盒取消限制(已开不退)

### kook_bot.py (3项)
- 原子写入(_atomic_json_save)、挑战排名限制+交换(rank_adjustment)+max_rounds=15、BOSS冷却泄漏清理

## 2026-06-29 代码重构 (全部验证: 输出hash d041cca7bff9891f与原版一致)

### battle_system.py (3,906→3,249, -657行)
- **合并3个攻击方法**: `execute_normal/skill/ultimate_attack` 378行重复 → `_execute_attack_core` 统一核心 + 薄包装
- **start_battle去重**: 箭头字典6处内联→`_DIRECTION_ARROWS`类常量; P10退场触发提取为`_trigger_retreat_effects`; P3触发循环提取为`_trigger_for_units`
- **删除僵尸渲染代码**: 末尾510行无调用方的GIF渲染函数 (BUFF_ICON_MAP保留, 被gif_renderer导入)
- **初始化防御**: `_player_unit_ids`/`_last_damage_info` 在`__init__`中初始化

### gif_renderer.py (1,833→1,699, -134行)
- **合并2个入口**: `battle_to_gif_new`+`battle_to_gif_bytes` 327行重复 → `_render_frames_from_result` 共享核心
- **箭头常量去重**: `COL_TO_ARROW_P/E` 从 `BattleSystem._PLAYER_ARROWS`/`_ENEMY_ARROWS` 派生

### qq_bot_ws.py (6,324→4,390, -1,934行)
- **elif→平铺if-return**: 路由链25层elif改为独立if-return块
- **删除fallback stub**: 32行except ImportError死代码→明确raise
- **_at_user辅助**: 17处@mention样板→`_at_user()`调用
- **图片合成→card_image.py**: 281行移出
- **盲盒→box_system.py**: 487行移出 (lazy import `_qq()`模式解决循环导入)
- **排行榜→ranking.py**: 1191行移出

## 战斗系统 (battle_system.py)

### 战场配置
- 5列战场, 初始部署3人占0/2/4列, 替补5+位置
- SP上限300, 必杀消耗100, 技能消耗30
- B+A合并为一个角色 (A卡属性合并到B卡)
- 同色加成1.05, 属性克制1.5/0.6, 超属性×1.2

### 优先级流程
- P1 开场被动 (仅上场3人, 位置[0,2,4])
- P2 替补入场 (继承阵亡位置, `_pending_dead_positions` 跨回合记录, needed限制)
- P3 行动开始时/敌方行动开始时
- P4 攻击决策+执行 (按速度排序: 必杀>技能>普攻)
- P5 被攻击时 (伤害/暴击/技能/必杀)
- P6 HP阈值 (50%/30%)
- P7 敌方SP满时 (defender_sp >= SP_MAX检查)
- P10 退场时 (遗言效果, _last_valid_position备份)

### A卡触发条件 (29种全接入)
自身/一对角色/队友/敌方/HP入场/复合条件 — 详见 `battle-system-trigger-update.md`
一对角色按position排序取相邻, 结果确定性

## GIF渲染系统 (gif_renderer.py)

### 渲染管线
`_render_frames_from_result` → `_parse_parsable_log`(优先)/`_parse_battle_log`(回退) → `_calculate_hp_changes` → `_render_team_section`×2 → `_render_sp_bars` → 编译GIF

### 帧布局
[事件描述]30px | [敌方队伍]216px | [Round X - Turn]22px | [SP条]24px | [玩家队伍]216px

### 帧类型
强制帧: round_start/sp_info/turn_switch/attack/enter/swap/battle_end/retreat/hp_threshold/trigger
状态去重: `_state_hash()` 计算 HP/alive/position/buffs/debuffs/is_broken 哈希

## QQ Bot 架构

- **SDK**: botpy WebSocket, PID文件锁防双开
- **图片服务**: 内置ThreadingHTTPServer(18080) + Cloudflare Tunnel, 健康自检自动重启
- **图床链路**: QQ ← CF Tunnel ← cloudflared ← localhost:18080 ← static_images/
- **GIF**: 缓存+hash复用, 每用户保留3个, 冷却3分钟, ~500KB, VS图发送后自动删除
- **systemd**: qqbot.service + qqbot-tunnel.service (Wants=非Requires=)
- **BOSS冷却**: BOSS_BATTLE_COOLDOWN字典, 24小时自动清理过期条目

## KOOK Bot 架构

- **SDK**: Flask Webhook
- **数据安全**: `_atomic_json_save` 原子写入 (临时文件+os.replace)
- **排行榜**: 动态战力排名 + rank_adjustment排名交换 + max_rounds=15限制
- **挑战限制**: 只能挑战比自己高且不超过3位的对手

## 命令参考

基础: 签到、获取呱太、十连/单抽、限定十连、昵称、个人记录
战斗: 战斗/对战、挑战<排名>、BOSS战、战斗日志/战斗GIF
配队: 队伍 我的卡[颜色/类型]、设置/切换/预设/自动/防守队
兑换: 兑换/兑换呱太/兑换红碎片/兑换蓝碎片、兑换<CODE>
排行榜: 排行榜、抽卡排行
其他: 三王女、三星池/红抽/蓝抽、/绑定<QQ号>、我的ID

## 数据安全原则
全量load → 修改特定字段 → _atomic_json_save(临时文件+os.replace原子替换), 绝不全量覆盖
QQ端和KOOK端均已实现原子写入

## 数据存储 (info/)
pity/gacha/signin/team/battle/cdkey/team_session_{user_id}.json, ranking.json, ranking_rewards.json, dau_log.json, backup/YYYY-MM-DD/

---

## 2026-07-02 变更记录（第二轮）

### 性能优化

| 优化项 | 说明 |
|--------|------|
| `asyncio.to_thread` 异步化 | 8个重操作 handler 改为异步执行：抽卡、战斗、BOSS、限定池、3星池、挑战、战斗日志等，避免阻塞主事件循环 |
| PIL 图片缓存 | `box_system.py` 中新增 `_pil_open` 缓存层，避免同一图片被重复磁盘IO读取 |
| `save_daily_stats` 降频 | 保存频率降低50倍（每50条消息保存一次），减少磁盘写入开销 |
| `settle_ranking_rewards` 去重 | 新增内存标志位，防止重复结算排行榜奖励 |
| `config.py IMAGE_HOST` mtime缓存 | 对图床地址的 mtime 检查增加缓存，减少文件系统调用 |
| `_bot_send` 线程安全改造 | 引入 `_MAIN_LOOP` + `call_soon_threadsafe`，确保从异步线程调用时的线程安全 |

### 战斗系统重构（方案4）

| 重构项 | 说明 |
|--------|------|
| half_turn 优先级流程重构 | 重新梳理半回合内的优先级执行流程，确保各阶段触发顺序正确 |
| DoT后P6 HP阈值检查 | 修复 DoT 伤害穿越 HP 阈值不触发 A 卡的 bug，在 DoT 结算后插入 P6 阈值判定 |
| 智能SP分配策略 | 优先保障拥有技能/必杀且可触发 A 卡的角色获得 SP，提升 A 卡触发率 |
| buff/debuff duration 到期修复 | 修复原代码 `b.duration <= 0 and b.duration != 0` 条件永远为 False 的逻辑 bug，使持续时间到期效果正常触发 |

### Bug修复

| 修复项 | 说明 |
|--------|------|
| `handle_team` / `handle_defense_team` / `handle_help` | 丢失的 handler 重新实现 |
| `handle_battle_log` / `_list_cached_gifs` | 从 `ranking.py` 重新导入，修复引用丢失 |
| `format_battle_result` / `format_boss_result` | 从 `ranking.py` 重新导入，修复引用丢失 |
| `BATTLE_SYSTEM_LOADED` / `IMAGE_HOST` / `_GIF_COOLDOWN` / `send_qq_gif` | `ranking.py` 中的跨模块引用改为 `_qq()` 延迟导入模式访问 |
| `_LAST_SETTLEMENT_CHECK` global 声明 | 修复缺少 `global` 声明导致的赋值异常 |
| `_ensure_char_dict` 类型转换 | `team_system.py` 中全面将 `characters` 类型从 `list` 转换为 `dict`，修复类型不一致问题 |
| `build_3star_cards_image` / `build_vs_team_image` | 添加 `_ensure_char_dict` 调用，确保 characters 类型统一 |

### 新功能：救援活动系统（レスキュー）

新增文件 `rescue_event.py`（1028行 + 阶段2扩展）。

#### 活动框架
- 管理员命令：开启活动、关闭活动、查看状态、发放救援券、刷新BOSS

#### BOSS挑战
- 5个BOSS（含Ex难度）
- Rank 1-9，HP倍率 1.0x - 3.0x
- 碎片掉落：Rank 1-3 掉落1个碎片，Rank 4+ 掉落4个碎片

#### 计分系统
- HS（Hero Score）/ RS（Rescue Score）双轨计分

#### 阶段2扩展
- 救援请求 / 协助机制
- 救援币系统
- 兑换商店

### 文件结构总览

| 文件 | 说明 |
|------|------|
| `qq_bot_ws.py` | 主 Bot 逻辑（WebSocket版） |
| `battle_system.py` | 战斗引擎 |
| `box_system.py` | 盲盒/抽卡系统 |
| `team_system.py` | 配队系统 |
| `ranking.py` | 排行榜 + 战斗 GIF |
| `card_image.py` | 卡牌图片生成 |
| `gif_renderer.py` | GIF 渲染 |
| `rescue_event.py` | 救援活动系统（**新增**） |
| `config.py` | 配置文件 |

---

## 2026-07-02 变更记录（第三轮）

### 我的卡筛选功能
- 队伍 我的卡 支持按颜色/类型筛选
- 支持格式：`队伍 我的卡 红`（颜色）、`队伍 我的卡 蓝B`（颜色+类型缩写）、`队伍 我的卡 超黄A`（超属性+支援）
- A=支援, B=战斗
- 筛选状态保存在 session，翻页自动保持
- 输出中"黄"显示为"金"（避免QQ敏感词过滤）
- `金` 和 `黄` 都可作为筛选关键字

### 救援活动系统 阶段2完成
- 救援请求：`救援 求助` 对未击杀BOSS发出请求（60分钟冷却）
- 救援公告板：`救援 列表` 查看待救援BOSS
- 救援协助：`救援 协助 [编号]` 消耗救援券帮其他玩家打BOSS
- 救援币：击杀后获得1-3个
- 兑换商店：5种商品（挑战券/救援券/Ex卷/呱太/蓝碎片）
- 管理员发币：`活动 发币 用户 数量`
- 修复管理员发币命令正则匹配（用原始message保留空格）

### 救援活动系统 阶段3完成
- 排名报酬表：冠军~参与 6档奖励
- 活动结算：`活动 结算` 按 RS 排名发放奖励（呱太/蓝碎片/救援币）
- 历史记录：保存到 info/rescue_event_history.json
- 活动过期自动检测
- 排名详情：`活动 排名` / `救援 排名` 扩展为RS+奖励预览
- 奖励预览：`救援 奖励` 查看排名报酬表

---

## 2026-07-03 变更记录

### RAID救援系统完全重构
- 命令前缀从"活动/救援"改为"raid"
- 完全重写 rescue_event.py，新BOSS系统：只有普通BOSS和EX BOSS两种
- BOSS初始HP 500万，EX固定4倍率(2000万)
- Rank n 奖励=9n救援币(EX=108)，击杀时按伤害%分配（向下取整）
- BOSS从config读取实际角色ID（BOSS_CARD_ID/RAID_EX_BOSS_CARD_ID）
- 玩家命令：raid/raid召唤N/raid召唤ex/raid列表/raid公告/raid求助N/raid挑战N/raid协助N/raid排行/raid兑换xx数量
- 管理员命令：raid开启/raid关闭/raid状态/raid结算/raid发券
- 队伍检查：必须使用raid槽位(7-11)，每队每日最多5次，队伍血量跨局保存
- 挑战锁定：BOSS同时只能被一人挑战，队列机制

### 队伍系统扩展
- 预设槽位从6扩展到11（7-11为RAID槽位）
- 新增队伍复制命令：队伍 复制 x 到 y（支持1-11槽位）
- 自动配队添加raid去重参数（check_raid_duplicates），5支raid队角色不重复
- list_presets_info 显示raid槽位标注[RAID]
- 队伍切换支持双位数槽位(10-11)，raid槽位切换时提示

### 每日结算集成
- qq_bot_ws每日结算中加入raid重置：发10挑战券+10救援券、解锁队伍、重置挑战次数、HS结算到RS
- 管理员发券命令支持中英文类型名和多种格式

### 我的卡筛选功能
- 队伍 我的卡 支持按颜色/类型筛选（蓝B/超黄A缩写格式）
- 翻页保持筛选状态，"黄"显示为"金"避免敏感词

### Bug修复
- ranking.py添加_atomic_json_save函数定义（排行榜结算报错修复）

### 2026-07-03 变更记录（第三次补充）

#### Raid队锁定机制修复
- _get_active_slot_info 从预设加载活跃槽位队伍（原来用load_team_data获取的是编辑中队伍，导致锁定判断失效）
- 每个raid队每天跨所有BOSS共享5次挑战次数
- 队伍血量跨BOSS继承（打完BOSS A的剩余血量在打BOSS B时继续使用）
- 全灭或5次用完则当日锁定，每日结算时解锁刷新

#### Rank升级机制重做
- 删除RANK_UNLOCK_RS（RS阈值解锁），改为击杀解锁
- 每个玩家有max_rank字段（初始1），召唤的x阶boss被击杀后max_rank升为x+1（最高9）
- 活动周期内不刷新，活动结束后重置
- 击杀时自动升级并提示

#### Raid队血条显示
- build_team_image新增hp_data参数，在A卡下方绘制简易血条
- 队伍命令中自动读取raid血量数据传入
- 阵亡角色显示红色血条，存活角色显示绿色血条

#### 临时图片清理
- 6处send_message_with_image调用后添加os.unlink删除临时图片
- 防止我的卡/队伍图片占用大量磁盘空间

---

## 2026-07-03 变更记录（第二次补充）

### RAID BOSS配置修复
- config.py新增 RAID_BOSS_CARD_ID 和 RAID_EX_BOSS_CARD_ID 配置项
- BOSS card_id 优先级：RAID专用配置 > BOSS_CARD_ID > 默认值101630001
- EX BOSS优先级：RAID_EX_BOSS_CARD_ID > RAID_BOSS_CARD_ID > BOSS_CARD_ID > 默认值
- _build_boss_extra_chars 从实际角色数据读取属性（attack/defense/speed/attribute等），无数据时用默认值
- 召唤/挑战/协助时使用实际角色名显示（boss_name字段）
- BOSS数据中保存boss_card_id和boss_name，求助转公共列表时同步保留

### 到期自动结算
- daily_raid_reset中检测活动过期自动调用settle_event
- 结算完成后active=False，不再发券
- 发券命令正则匹配修复（支持无空格格式）

---

## 2026-07-03 变更记录（补充）

### RAID系统修复
- raid开启后到期自动结算：daily_raid_reset中检测活动过期自动调用settle_event
- 结算完成后不再发券（只在active=True时发券）
- ranking.py添加_atomic_json_save函数定义（排行榜结算报错修复）

### 2026-07-03 变更记录（第四次补充）

#### Raid显示优化
- raid列表和公告板显示BOSS实际名称（从boss_name字段读取）
- raid挑战/协助结果显示VS图（使用build_vs_team_image生成）
- VS图通过[RAID_VS_IMAGE]标记传递，qq_bot_ws自动检测并使用send_message_with_image发送

#### 队伍图缩小
- build_team_image背景尺寸从1920x1080缩小到1440x810
- 边距从100/150缩小到80/120

#### 队伍命令提示修正
- 所有"队伍切换 1~6"提示改为"队伍切换 1~11"
- 涵盖文档字符串、卡牌列表提示、切换格式提示、队伍显示提示、帮助面板

#### Raid队血量继承修复
- _simulate_battle从player_team中读取_raid_saved_hp数据
- 有保存血量时：阵亡角色不输出伤害，存活角色按数量计算伤害
- 返回正确的player_survived和player_units（含hp和alive字段）
- 恢复队伍时将saved_hp通过_raid_saved_hp字段附带在team_data中
- 挑战/协助两处恢复逻辑均已修复

#### Raid队锁定保护
- 自动配队/设置/清除/清空命令前检查raid锁定状态
- 已锁定的raid队拒绝修改并提示

#### ImageDraw导入修复
- build_team_image中添加from PIL import ImageDraw（修复血条绘制报错）

### 2026-07-03 变更记录（第五次补充）

#### 配队系统修复
- 队伍设置命令（队伍 设置 位置 序号）现在传入筛选参数（filter_color/filter_type）
- 修复筛选状态下选卡与实际放置卡不一致的bug：用户在筛选后看到的卡序号与设置命令获取的列表一致

#### RAID昵称显示
- 新增_get_display_name辅助函数：优先使用玩家昵称，无昵称则截取ID前6位
- RAID排行榜（RS/HS）显示玩家昵称
- RAID公告板求助者显示昵称
- RAID活动状态玩家概览显示昵称
- RAID结算排名显示昵称

### 2026-07-03 变更记录（第六次补充）

#### 击杀奖励超额伤害修复
- damage_dealt在记录前cap到BOSS当前剩余HP（min(damage_dealt, boss_hp)）
- 挑战和协助两处均已修复，奖励分配不再出现超过100%的伤害

#### Raid队血量继承重做
- _simulate_battle完全重写：统一处理有/无保存血量的情况
- 每个存活角色造成3-7%伤害（基于存活数）
- 每个存活角色损失20-50%HP，10%概率死亡
- 返回正确的player_units（含更新后的hp和alive字段）
- 下次战斗从上次剩余血量继续

#### HS改用绝对伤害值
- HS从伤害百分比改为绝对伤害值（damage_dealt）
- 排行榜、活动状态、个人进度显示格式去掉%号
- RS累计的是每日HS（绝对值）的累计

#### 活动结束后数据清除
- settle_event结算后清除所有玩家的：票券、HS/RS、max_rank、BOSS列表、队伍血量、挑战次数
- 只保留救援币（rescue_coins）

#### Raid帮助命令
- 新增raid帮助/raid help命令
- 显示所有玩家命令说明、队伍系统规则、奖励规则

#### 昵称显示补充
- 击杀奖励分配信息使用玩家昵称

---

### 2026-07-03 变更记录（第七次补充）

#### RAID战斗系统重构（复用BOSS战）
- battle_system.start_boss_battle新增player_initial_hp参数（{card_id: hp}）
- battle_system.start_boss_battle新增boss_hp_override参数（覆盖BOSS血量）
- 战斗前临时修改角色HP（从self.characters），战斗后恢复
- RAID挑战/协助传入player_initial_hp和boss_hp_override
- 阵亡角色HP设为0，战斗系统自动标记为死亡
- _simulate_battle保留为fallback，但正常流程使用真实战斗系统

### 2026-07-03 变更记录（第八次补充）

#### 血量继承根因修复
- 根因：player_units先B后A且跳过None，保存时按顺序存hp_list，但恢复时按battle_cards索引取——索引错位导致血量数据对应不上
- 修复保存逻辑：按battle_cards的6个位置对齐保存（用position字段反向映射到bc索引）
- battle_position_map={0:0, 2:1, 4:2, 5:3, 6:4, 7:5}反向映射
- 挑战和协助两处保存逻辑均已修复

#### 队伍命令显示槽位
- 队伍图片上方显示当前是第几队（如"当前: 第7队 (RAID)"）
- RAID槽位(7-11)标注(RAID)标签

### 2026-07-03 变更记录（第九次补充）

#### 血量保存增加max_hp
- team_hp_saved新增max_hp字段，记录每个位置B卡的最大HP
- 挑战和协助两处保存逻辑均已更新

#### 血条显示改进
- 使用HP/max_hp计算实际百分比，不再固定60%
- 三色血条：>50%绿色，>25%黄色，≤25%红色
- 阵亡角色显示全红色

#### VS图BOSS位置居中
- RAID挑战/协助的VS图中BOSS放在第3列（索引2，0-4的中间位置）
- 敌方队伍battle_cards改为[None, None, boss_card_id, None, None, None]

### 2026-07-03 变更记录（第十次补充）

#### 血量继承根因修复（最终版）
- 真正根因：build_battle_team在B+A属性合并后，会重置battle_unit.current_hp和max_hp为total_hp（满血）
- 之前的方案（修改character.hp）在build_battle_team之后被覆盖，所以无效
- 修复：给start_battle添加player_hp_override参数，在build_battle_team之后、战斗开始前应用
- HP=0的角色设为alive=False（阵亡不参战）
- start_boss_battle通过player_hp_override传递，删除旧的修改character.hp逻辑

#### BOSS击败后移除列表
- 挑战击杀：从my_bosses和public_board两个列表移除已击杀BOSS
- 协助击杀：从拥有者的my_bosses和data.public_board移除
- _distribute_kill_rewards中也有移除逻辑（现在冗余但无害）
