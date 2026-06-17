# ZMDBot Discord Version

基于 Discord 的自动抽卡机器人，支持抽卡、战斗等完整功能。

## 📋 功能特点

- 🎴 **抽卡系统**：支持单抽和十连抽，包含保底机制
- ⚔️ **战斗系统**：回合制战斗，支持GIF回放
- 🏰 **BOSS战斗**：挑战BOSS获得奖励
- 👥 **队伍系统**：配队、预设、防御队伍
- ✅ **签到系统**：每日签到获取呱太
- 🏆 **排行榜**：战力排行、抽卡榜单
- 🪙 **呱太系统**：货币系统，用于抽卡

## 🛠️ 配置 Discord App

### 步骤1：创建 Discord Application

1. 访问 [Discord Developer Portal](https://discord.com/developers/applications)
2. 点击 **"New Application"** 创建新应用
3. 输入应用名称（如 "ZMDBot"），点击 **"Create"**

### 步骤2：设置 Bot

1. 在左侧菜单点击 **"Bot"**
2. 点击 **"Add Bot"**，确认创建
3. 开启以下权限：
   - **Message Content Intent**
   - **Server Members Intent**
4. 点击 **"Reset Token"**，复制生成的 Token（稍后会用到）

### 步骤3：配置权限

1. 在左侧菜单点击 **"OAuth2"** → **"URL Generator"**
2. 在 **"Scopes"** 中勾选：
   - `bot`
   - `applications.commands`
3. 在 **"Bot Permissions"** 中勾选：
   - `Send Messages`
   - `Embed Links`
   - `Attach Files`
   - `Read Message History`
4. 复制生成的 URL，在浏览器中打开邀请机器人到你的服务器

### 步骤4：配置机器人

1. 复制 `config.example.json` 为 `config.json`
2. 编辑 `config.json`：
   ```json
   {
       "TOKEN": "你的Bot Token",
       "OWNER_ID": 你的Discord用户ID,
       "GUILD_ID": 你的服务器ID（可选，用于快速同步命令）
   }
   ```

### 步骤5：运行机器人

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python discord_bot.py
```

## 📖 命令列表

### 抽卡命令

| 命令 | 描述 | 参数 |
|------|------|------|
| `/gacha` | 单抽一次 | 无 |
| `/tenpull` | 十连抽 | 无 |
| `/collection` | 查看卡牌收藏 | 无 |
| `/pity` | 查看保底进度 | 无 |

### 战斗命令

| 命令 | 描述 | 参数 |
|------|------|------|
| `/battle` | 进行普通战斗 | 无 |
| `/boss` | 挑战BOSS | boss_id（可选） |
| `/battlegif` | 生成战斗GIF | 无 |

### 队伍命令

| 命令 | 描述 | 参数 |
|------|------|------|
| `/team` | 查看当前队伍 | 无 |
| `/setteam` | 设置战斗队伍 | card1, card2, card3 |
| `/autoteam` | 自动配队 | 无 |
| `/presets` | 管理队伍预设 | 无 |

### 社交命令

| 命令 | 描述 | 参数 |
|------|------|------|
| `/signin` | 每日签到 | 无 |
| `/balance` | 查看呱太余额 | 无 |
| `/rankings` | 查看排行榜 | 无 |
| `/profile` | 查看个人资料 | 无 |

### 管理命令

| 命令 | 描述 | 参数 |
|------|------|------|
| `/reload` | 重新加载数据 | 无（仅管理员） |
| `/backup` | 备份数据 | 无（仅管理员） |

## 📁 项目结构

```
discord/
├── discord_bot.py          # 主机器人代码
├── config.json             # 配置文件
├── config.example.json     # 配置示例
├── requirements.txt        # 依赖列表
├── README.md               # 使用说明
└── data/                   # 用户数据目录（自动创建）
```

## 🚀 依赖

```
discord.py>=2.0
Pillow>=9.0
openpyxl>=3.0
requests>=2.31.0
```

## 🔧 开发说明

### 获取用户ID

1. 在Discord设置中开启 **"开发者模式"**
2. 右键点击用户头像，选择 **"Copy ID"**

### 获取服务器ID

1. 在Discord设置中开启 **"开发者模式"**
2. 右键点击服务器图标，选择 **"Copy ID"**

## 📝 注意事项

1. 确保上级目录存在 `cards_completed.xlsx`（角色数据）
2. 确保上级目录存在 `iconimage/`（角色图标）
3. 首次运行会自动创建数据目录
4. 机器人需要管理员权限才能使用管理命令

## 📄 许可证

MIT License