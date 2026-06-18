---
name: gif-renderer-fixes
description: 2026-06-18 GIF渲染器6项修复：HP同步、特殊效果、初始BUFF、败方全灭、阵亡清场、SP条
metadata: 
  node_type: memory
  type: reference
  updated: 2026-06-18
  originSessionId: 58fdfc42-ab8f-40b2-aa92-7682f9a135f6
---

# GIF渲染器修复记录 (2026-06-18)

## Fix 1: 攻击帧HP同步
**问题**: attack事件不读取position数据更新HP，攻击帧显示旧血量
**修改**: `gif_renderer.py` attack handler — save_frame前遍历player_positions/enemy_positions更新hp/max_hp/alive/hp_change
**位置**: `_parse_parsable_log` attack分支 ~1100行

## Fix 2A: 特殊效果可视化(gif_renderer)
**问题**: hit_status字段(盾抵挡/反射/回避/不屈)未被读取显示
**修改**: attack handler读取position中的hit_status，按2字符中文token解析，追加到event_text
**格式**: `"角色 → 目标: 伤害 [目标: 盾抵挡+反射]"`

## Fix 2B: 特殊效果数据源(battle_system)
**问题**: execute_skill_attack/execute_ultimate_attack不填充_last_damage_info，回避/不屈未追踪
**修改**:
- `get_hit_status()`: 新增dodged→"回避", tenacious→"不屈"
- `execute_normal_attack()`: 回避/{dodged:True}, 不屈/{tenacious:True}
- `execute_skill_attack()`: 回避/盾/伤害/不屈分支全部写入_last_damage_info
- `execute_ultimate_attack()`: 同上

## Fix 3: 初始帧清空BUFF
**问题**: A卡预触发(start_battle第2389-2396行)在round_start前施加buff，未生成parsable条目，导致开局帧就有BUFF
**修改**: initial_set分支 — save_frame("战斗开始")前清空所有单位的buffs/debuffs

## Fix 4: 战斗结束败方全灭
**问题**: battle_end只保存状态不标记败方阵亡
**修改**: battle_end handler — 根据winner将败方所有单位标记为alive=False, hp=0, buffs=[], debuffs=[]

## Fix 5: (被Fix 3覆盖)
换位前BUFF问题与Fix 3同根，一并解决

## Fix 6: 阵亡角色及时清场 + 替补上场替换
**问题**: 死单位持续显示在场上，替补未正确替换
**修改**:
- attack handler: save_frame后死单位position=-1, buffs=[], debuffs=[]
- enter handler: 替补上场时显式清空buffs=[], debuffs=[]

## Fix 7: SP条实时显示
**问题**: GIF无SP信息
**修改**:
- `_parse_parsable_log`: 新增sp_info事件处理，update player_sp/enemy_sp并同步单位状态
- `save_frame`: frame_data包含player_sp/enemy_sp
- 新增`_render_sp_bars()`: 渲染蓝(P-SP)/红(E-SP)双SP条
- `battle_to_gif_new`/`battle_to_gif_bytes`: 帧高度+28px(SP_BAR_HEIGHT)，布局添加SP条

## 关键教训
- parsable_log的每个事件都包含完整的player_positions/enemy_positions，需要在每个handler中同步
- hit_status是2字符中文token拼接(如"抵挡反射")，解析时按2字符步进
- 战斗系统对skill/ultimate攻击不追踪_last_damage_info是数据源缺失
- A卡预触发绕过_log()直接修改单位，导致parsable状态与视觉不一致
- `[dict(u) for u in p_field]`是浅拷贝，修改原dict会影响后续帧(这正是我们想要的)
- position=-1的单位不会出现在_render_team_section的5列布局中
