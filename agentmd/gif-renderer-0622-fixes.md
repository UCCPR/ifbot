---
name: gif-renderer-0622-fixes
description: 2026-06-22 GIF渲染器修复：攻击内A卡事件文本、retreat帧处理器
metadata: 
  node_type: memory
  type: project
  updated: 2026-06-22
  originSessionId: ea624bfe-a37a-4fd5-8dbc-9e2a3d010bea
---

# GIF渲染器修复 (2026-06-22)

## 攻击内A卡 assist_trigger 事件文本修复
- **问题**: 攻击内触发的A卡效果 `_log(line, {"type": "assist_trigger", "phase": "attack_internal"})` 缺少 `assist_name`/`effects`/`source_unit` 字段 → GIF事件文本显示 `": 效果触发"`
- **修复**: 
  - `battle_system.py`: 解析效果行 → 提取 `target_name` + `effect_desc` + `is_attack_internal` 标志
  - `gif_renderer.py`: `assist_trigger` 处理器新增 `is_attack_internal` 分支，直接渲染 `"A卡 → 目标: 效果描述"`

## retreat 帧处理器 (新增)
- **问题**: `retreat` 是强制帧类型但 GIF 渲染器无对应 handler → 退场瞬间帧丢失
- **修复**: 新增 `elif entry_type == "retreat"` 处理器:
  - 从 player_positions/enemy_positions 检测 alive=False 的单位
  - 清空其 position=-1、buffs/debuffs
  - 构建退场事件文本 `"退场: 角色1, 角色2"`

## 未修复
- `hp_threshold` 强制帧仍无处理器 (用户要求跳过)
- `trigger`/`dot_damage`/`stun_recover`/`debuff_trigger`/`buff_expiry` 非强制帧无处理器 (低优先级，状态变化由后续强制帧捕获)
