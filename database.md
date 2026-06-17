# KOOK抽卡机器人开发文档

## 项目概述
基于QQ版抽卡机器人实现KOOK版，包含完整的抽卡机制、队伍系统、战斗系统等功能。

---

## 核心问题与解决方案

### 问题1：KOOK版功能缺失
**用户提问**：这些开发中的所有功能在QQ版中都有实现，参照实现

**解决方案**：
- 实现防守队功能（handle_defense_team）
- 实现BOSS战功能（handle_boss_battle）
- 实现排行榜功能（handle_ranking）
- 实现抽卡榜单功能（handle_gacha_leaderboard）
- 实现碎片兑换功能（handle_exchange_crystal）
- 实现三星池子功能（handle_3star_pool）
- 实现挑战排名功能（handle_challenge）
- 实现详细信息功能（handle_show_details）

### 问题2：图片发送失败
**用户提问**：聊天框依旧没有收到生成的角色图

**解决方案**：
- 使用KOOK的`/api/v3/asset/create`接口先上传图片获取`file_id`
- 在消息内容中使用`[file=file_id]`格式引用图片

### 问题3：池子规则不一致
**用户提问**：KOOK版的池子规则和QQ版不一样，改回去

**解决方案**：
- 单抽价格：300呱太
- 十连价格：3000呱太（冷却60秒）
- 限定十连：15000呱太（冷却8分钟）
- 抽卡概率：1星72%、2星23%、3星5%
- 保底机制：每150抽必出フェス限定3星

### 问题4：命令需要斜杠前缀
**用户提问**：要求呼叫机器人的时候有斜杠/，避免误触

**解决方案**：
- 修改命令处理逻辑，所有命令必须以`/`开头
- 示例：`/单抽`、`/十连`、`/帮助`

### 问题5：配置文件错误
**用户提问**：请先在 config.json 中设置 KOOK Bot Token！

**解决方案**：
- 创建config.json配置文件
- 配置项包括：BOT_TOKEN、WEBHOOK_SECRET、VERIFY_TOKEN、ENCRYPT_KEY等

### 问题6：抽卡失败（KeyError）
**用户提问**：KeyError: 'card_collection'

**解决方案**：
- 在handle_gacha函数中添加card_collection的默认值检查
- 确保用户数据结构完整

### 问题7：BASE_DIR未定义
**用户提问**：NameError: name 'BASE_DIR' is not defined

**解决方案**：
- 将`BASE_DIR = Path(__file__).parent`移到load_config()函数之前

### 问题8：存档机制分析
**用户提问**：仔细阅读QQ版gachabot代码，每一个部分什么作用都要分析出来然后在kook实现，存档是怎么实现的，有备份吗

**解决方案**：
- 抽卡记录：`pity_{user_id}.json`
- 呱太数据：`gacha_{user_id}.json`
- 签到数据：`signin_{user_id}.json`
- 队伍配置：`team_{user_id}.json`
- 排行榜：`ranking.json`
- 每日自动备份到`backup/YYYY-MM-DD/`目录

---

## 模块架构

### 1. 配置模块
- 目录路径定义（BASE_DIR、INFO_DIR、OUTPUT_DIR、BACKUP_DIR）
- 配置加载（从config.json读取）

### 2. 日志模块
- log_info() - 记录普通信息
- log_error() - 记录错误信息

### 3. 备份模块
- get_last_backup_date() - 获取最后备份日期
- set_last_backup_date() - 设置备份日期
- backup_pity_records() - 执行每日备份

### 4. 抽卡记录模块
- load_pity_data() - 加载抽卡记录
- save_pity_data() - 保存抽卡记录
- update_pity() - 更新保底计数
- get_remaining_pity() - 获取保底剩余次数

### 5. 呱太数据模块
- load_gacha_data() - 加载呱太数据
- save_gacha_data() - 保存呱太数据
- get_gacha_count() - 获取呱太数量
- add_gacha() - 增加呱太
- spend_gacha() - 消耗呱太

### 6. 签到模块
- load_signin_data() - 加载签到数据
- save_signin_data() - 保存签到数据
- can_signin() - 检查是否可签到
- signin() - 执行签到

### 7. 抽卡机制模块
- gacha_draw() - 执行抽卡
- draw_mystery_box() - 抽取盲盒
- apply_mutation() - 应用突变
- select_3star_character() - 选择三星角色

### 8. 卡牌绘制模块
- composite_card() - 合成卡牌图片
- get_level_image() - 获取星级背景/框
- find_attribute_icon() - 查找属性图标
- find_type_icon() - 查找类型图标

### 9. 队伍系统模块（导入team_system.py）
- load_team_data() - 加载队伍数据
- save_team_data() - 保存队伍数据
- auto_build_team() - 自动配队
- set_team_card() - 设置队伍卡牌

### 10. 战斗系统模块（导入battle_system.py）
- BattleSystem - 战斗系统类
- format_battle_result() - 格式化战斗结果
- format_boss_result() - 格式化BOSS战结果

### 11. 排行榜模块
- load_ranking_data() - 加载排行榜
- save_ranking_data() - 保存排行榜

### 12. 命令处理模块
- handle_command() - 命令分发
- handle_gacha() - 抽卡处理
- handle_signin() - 签到处理
- handle_team() - 队伍处理
- handle_battle() - 战斗处理

---

## 文件结构

```
zmdbot/
├── kook_bot.py          # KOOK机器人主程序
├── config.json          # 配置文件
├── team_system.py       # 队伍系统模块
├── battle_system.py     # 战斗系统模块
├── iconimage/           # 角色图标
├── level/               # 星级背景/框/图标
├── info/                # 用户数据目录
│   ├── gacha_*.json     # 呱太数据
│   ├── pity_*.json      # 抽卡记录
│   ├── signin_*.json    # 签到数据
│   ├── team_*.json      # 队伍配置
│   └── ranking.json     # 排行榜
├── output/              # 输出目录
└── backup/              # 备份目录
    └── YYYY-MM-DD/      # 每日备份
```

---

## 抽卡机制

### 概率配置
| 星级 | 权重 | 概率 |
|------|------|------|
| 1星 | 72 | ~72% |
| 2星 | 23 | ~23% |
| 3星 | 5 | ~5% |

### 保底机制
- 每150抽必出フェス限定3星
- 十连保底：至少出1张2星卡

### 盲盒系统
- 黑色盲盒概率：2%
- 黑色盲盒必定是2星或3星（65%/35%）

### 突变机制
| 突变方向 | 概率 |
|----------|------|
| 1星→2星 | 8% |
| 1星→3星 | 2% |
| 2星→3星 | 5% |
| 不突变 | 88% |

### 三星内部分配
| 类型 | 概率 |
|------|------|
| フェス限定 | 25% |
| 期間限定 | 35% |
| 其他三星 | 40% |

---

## 命令列表

| 命令 | 消耗 | 说明 |
|------|------|------|
| `/单抽` | 300呱太 | 普通抽卡 |
| `/十连` | 3000呱太 | 冷却60秒 |
| `/限定十连` | 15000呱太 | 冷却8分钟，必出限定 |
| `/签到` | 无 | 获得30000呱太 |
| `/获取呱太` | 无 | 获得10000呱太，冷却60秒 |
| `/队伍` | 无 | 查看队伍 |
| `/队伍 自动配队` | 无 | AI自动配队 |
| `/防守队` | 无 | 查看/设置防守队 |
| `/战斗` | 无 | AI对战 |
| `/BOSS战` | 无 | 挑战BOSS |
| `/排行榜` | 无 | 战力排行榜 |
| `/抽卡榜单` | 无 | 抽卡排行榜 |
| `/个人记录` | 无 | 详细统计信息 |
| `/帮助` | 无 | 显示帮助 |

---

## 配置项说明

```json
{
    "WEBHOOK_SECRET": "",
    "BOT_TOKEN": "",
    "VERIFY_TOKEN": "",
    "ENCRYPT_KEY": "",
    "HOST": "0.0.0.0",
    "PORT": 5000,
    
    "PITY_LIMIT": 150,
    "GACHA_COST": 300,
    "GACHA10_COST": 3000,
    "GACHA10_COOLDOWN_SECONDS": 60,
    "LIMITED_GACHA_COST": 15000,
    "LIMITED_GACHA_COOLDOWN_SECONDS": 480,
    "GET_GACHA_REWARD": 10000,
    "DAILY_REWARD": 30000,
    
    "MYSTERY_BOX_CHANCE": 0.02,
    "MUTATION_NO_CHANGE": 0.88,
    "MUTATION_1_TO_2": 0.08,
    "MUTATION_1_TO_3": 0.02,
    "MUTATION_2_TO_3": 0.05,
    
    "FES_LIMIT_PROB": 0.25,
    "PERIOD_LIMIT_PROB": 0.35,
    "OTHER_3STAR_PROB": 0.40
}
```

---

## 启动方式

1. 在config.json中设置BOT_TOKEN
2. 运行：`python kook_bot.py`
3. 监听地址：`http://localhost:5000/webhook`

---

## 版本历史

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-06-16 | v1.0 | 初始版本，实现核心抽卡功能 |

---

## 注意事项

1. 确保iconimage目录下有角色图标文件
2. 确保level目录下有星级背景/框/图标文件
3. 首次启动会自动创建必要的目录结构
4. 每日第一次启动会自动备份所有用户数据

---

**文档更新日期**：2026-06-16
**作者**：AI Assistant
