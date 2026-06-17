# 项目上下文记忆

## 项目定位
魔法禁书目录幻想收束卡牌游戏模拟器，基于QQ机器人运行

## 核心模块

### 1. 战斗系统 (battle_system.py)
- 重构自model文件夹的战斗模拟器
- 核心伤害公式: 攻击² / (攻击 + 防御)
- 属性克制: 红→绿→蓝→红循环，黄↔紫互克
- SP系统: 阵营共用，必杀100SP，技能30SP
- 回合流程: 先手方全员行动 → 后手方全员行动
- 换位机制: 角色可以通过换位改变位置
- 替补上场: 阵亡角色可以被替补替换
- 受击状态: 记录抵挡、反射、吸收、减伤等效果

### 2. 抽卡系统 (gacha_bot.py)
- 支持多卡池（限定池、友情池等）
- 保底机制（pity系统）
- 角色星级: 1-5星

### 3. 队伍系统 (team_system.py)
- 6角色队伍（3B+3A）
- 同位置B+A同色增益10%
- 5列战场布局（位置0-4）

### 4. 排位系统
- 10人排行榜
- 只能挑战排名比自己高且不超过3位的对手

### 5. GIF生成系统 (gif_renderer.py)
- 从战斗日志生成GIF动画
- 5列战场布局（位置0-4）
- 每方同时最多3个角色在场上（初始位置0/2/4）
- 支持换位和替补上场解析
- 支持攻击方向标注（箭头方向）
- 支持攻击类型标注（[普/技/终/A]）
- 支持受击状态标注（抵挡/反射/吸收/减伤）
- 使用Windows系统字体路径

## 数据结构

### Character（角色）
- card_id, name, hp, attack, defense, speed
- attribute（红/绿/蓝/黄/紫）
- attack_type（物理/异能）
- attack_directions（攻击方向）
- skill, ultimate（技能对象）
- assist_effect1/2（A卡效果）
- passives（潜能）

### BattleUnit（战斗单位）
- character（角色引用）
- position（位置0-4，场上位置，-1表示替补队列）
- current_hp, max_hp
- skill_cooldown（技能冷却）
- buffs, debuffs（状态列表）
- assist_unit（关联的A卡）

### Skill（技能）
- name, description
- sp_cost, cooldown
- power_rank（威力等级）
- area（作用范围）
- effects（效果列表）
- power_up_type（威力上升类型）

### AssistEffect（支援效果）
- trigger_count（触发次数）
- trigger_time（触发时机）
- area（作用范围）
- effects（效果列表）

## 关键路径

### 战斗流程
1. start_battle() → 初始化队伍
2. 回合循环 → A卡触发 → 行动排序 → 执行攻击
3. execute_normal_attack/execute_skill_attack/execute_ultimate_attack
4. calculate_damage() → 计算伤害
5. _handle_counter_effects() → 处理反射/天罚
6. _check_shield() → 检查护盾抵挡
7. 返回战斗结果

### GIF生成流程
1. _parse_parsable_log() → 解析程序化日志
2. init_field_from_log() → 初始化场上单位
3. _calculate_hp_changes() → 计算HP变化
4. save_frame() → 保存每帧状态
5. battle_to_gif_new() → 生成GIF动画
6. _render_team_section() → 渲染队伍区域
7. _render_character_card() → 渲染角色卡片

## 配置参数

### 必杀威力等级
- 小: 1.2, 中: 1.5, 大: 1.7
- 特大: 2.0, 极大: 2.3, 超特大: 2.5

### 属性克制倍率
- 克制: 1.5
- 被克制: 0.6
- 超属性额外: 1.2

### SP配置
- SP_MAX: 300
- ULT_COST: 100
- SKILL_COST: 30
- SP_PER_ATTACK: 15
- SP_PER_DAMAGED: 10

### 战场配置
- 位置0: 左下（↙/↖）
- 位置1: 左中（←/←）
- 位置2: 中间（↓/↑）
- 位置3: 右中（→/→）
- 位置4: 右下（↘/↗）
- 场上最多5个位置，但初始只上场3人（位置0/2/4）
- 位置1/3为空位，可通过换位使用
- 替补队列: position=-1

## 资源路径
- 角色立绘: iconimage/card_cutin_{card_id}.png
- 状态图标: state_icon/state_icon_{name}_{UP/DOWN}.png
- 背景图: level/bg_000001002.png
- 卡牌框架: level/gacha_tmb_*.png
- 输出目录: output/

## 数据存储
- 战斗记录: info/battle_{user_id}.json（滚动保留3次）
- 抽卡记录: info/gacha_{user_id}.json
- 队伍配置: info/team_{user_id}.json
- 排行榜: info/ranking.json
- 日志文件: info/*.log
- 备份目录: backup/battle_logs/日期/

## 命令系统

### 战斗命令
- 挑战 排名 → 挑战排行榜对手
- 战斗日志 → 查看战斗记录
- 战斗GIF → 生成战斗动画
- 备份战斗录 → 管理员备份战斗日志

### 抽卡命令
- 抽卡/十连 → 抽取卡牌
- 卡池 → 查看卡池信息

### 队伍命令
- 队伍 → 查看队伍
- 编队 → 编辑队伍
- 自动配队 → AI自动配队

## 日志格式

### 普通攻击日志
```
(0.85)攻击者名字[箭头] -> 目标名字[箭头] (伤害) [普通攻击]
```

### 技能攻击日志
```
(1.5)攻击者名字[箭头] -> 目标名字[箭头] (伤害) [技能]
```

### 必杀技日志
```
(2.0)攻击者名字[箭头] -> 目标名字[箭头] (伤害) [必杀技]
```

### 换位日志
```
[换位] [P/E] 角色名字[箭头] -> 新箭头
```

### 替补上场日志
```
[上场] [P/E] 角色名字[箭头]
```

### 回合切换日志
```
[Player turn]
[Enemy turn]
```

### 反射/抵挡日志
```
天罚发动！角色名抵挡X伤害，攻击者被眩晕！
矢量操作反射！攻击者受到X物理伤害
```

## GIF生成器状态

### 已实现功能
- 5列战场布局（位置0-4）
- 角色卡片渲染（使用gacha_tmb_frame.png）
- 血条显示
- BUFF图标显示
- 扣血/加血提示（带[普/技/终/A]标注）
- 攻击方向标注（箭头方向）
- 回合信息（Round X - Player/Enemy Turn）
- 胜利信息（Player WIN!/Enemy WIN!/Draw!）
- 程序化日志包含位置、HP、HP变化、BUFF、受击状态信息
- Windows系统字体支持
- 受击状态标注（抵挡/反射/吸收/减伤）

### 待修复问题
- 无

## 程序化日志格式

每条日志条目包含：
```json
{
  "type": "round_start/sp_info/turn_switch/attack/...",
  "content": "...",
  "player_positions": [
    {
      "name": "角色名[箭头]", 
      "position": 0, 
      "alive": true, 
      "hp": 10000, 
      "max_hp": 10000,
      "hp_change": -1800,
      "hit_status": "抵挡",
      "buffs": [{"name": "攻击", "magnitude": "大"}],
      "debuffs": []
    }
  ],
  "enemy_positions": [...]
}
```

### 受击状态字段说明
- **hp_change**: HP变化值（正数=加血，负数=扣血）
- **hit_status**: 受击状态，可能包含：
  - 抵挡: 被护盾抵挡
  - 反射: 触发了反射效果
  - 吸收: 伤害被吸收
  - 减伤: 受到减伤效果影响

---
最后更新: 2026-06-16
