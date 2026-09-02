# TOARU Bot - 幻想收束的模拟抽卡bot

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-Apache%202.0-blue)

《魔法禁书目录 幻想收束》抽卡、配队与战斗模拟机器人。当前主要运行方式是基于 QQ 官方 Bot API 的 WebSocket 客户端，同时保留 NapCat、QQ 回调和 KOOK 入口。

> 本项目仅供个人学习与技术研究，不得用于商业用途。

## 功能

- 单抽、十连、限定池、FES 保底与十连二星保底，复刻if卡池（我尽力了
- 盲盒开箱、黑色盲盒和星级突变
- 卡牌收藏、红蓝碎片、三星兑换池和 CDKEY
- 每日签到、呱太经济、个人记录和全服统计
- 6 个战斗位 + 6 个支援位，多套队伍预设与自动配队
- PVE、PVP、BOSS、排行榜和排位奖励
- 战斗文本日志与动态 GIF 渲染
- Raid/救援活动系统
- JSON 原子写入、并发保护、每日备份和存储清理
无敌了孩子们
![战绩截图](RMIMAGE/战绩.png)
群友们一天抽了一万多次，鉴定为纯血ifp👍
## 如何食用

| 文件 | 用途 | 建议 |
| --- | --- | --- |
| `qq_bot_ws.py` | QQ 官方 Bot WebSocket 版 | 当前主入口 |
| `qq_bot.py` | QQ 官方回调版 | 兼容入口 |
| `gacha_bot.py` | NapCat/OneBot 版 | 旧部署兼容 |
| `kook_bot.py` | KOOK 版 | 独立配置 |

以下部署说明默认使用 `qq_bot_ws.py`。

## 快速开始

### 1. 准备环境

- Python 3.8+
- QQ 开放平台 Bot 的 AppID、Token 和 Secret
- 用于 QQ 下载图片的公网 HTTPS 地址（可选固定域名或 Cloudflare Tunnel）

```bash
git clone https://github.com/UCCPR/ifbot.git
cd ifbot

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell 激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. 创建配置

Linux/macOS：

```bash
cp config.example.py config.py
```

Windows PowerShell：

```powershell
Copy-Item config.example.py config.py
```

然后编辑 `config.py`，至少填写：

```python
QQ_BOT_APP_ID = "..."
QQ_BOT_TOKEN = "..."
QQ_BOT_SECRET = "..."
ADMIN_QQ = "..."
```

`config.py` 包含真实凭证，已被 `.gitignore` 排除，不要将它提交到任何公开仓库。

### 3. 配置图片服务

机器人内置图片 HTTP 服务，默认端口为 `18080`。`IMAGE_HOST` 应填写能够转发到该端口的公网 HTTPS 地址：

```python
IMAGE_HOST = "https://images.example.com"
```

- 已有固定域名：将反向代理或 Cloudflare Named Tunnel 指向 `http://127.0.0.1:18080`。
- 没有固定域名：`start_qq_bot.sh` 可启动 Cloudflare Quick Tunnel，并更新 `config.py` 中的地址。

### 4. 前台运行

```bash
python3 qq_bot_ws.py
```

首次启动建议使用前台模式，确认 Bot 连接、Excel 数据、图片服务和存档读写正常。

## Linux 服务部署

仓库内的 systemd 脚本默认项目路径为 `/home/root/zmdbot`。如果使用其他路径，请先修改 `qqbot.service` 和 `setup_services.sh` 中的路径。

```bash
sudo mkdir -p /home/root
sudo git clone https://github.com/UCCPR/ifbot.git /home/root/zmdbot
cd /home/root/zmdbot

sudo pip3 install -r requirements.txt
cp config.example.py config.py
# 编辑 config.py

sudo bash setup_services.sh
```

常用维护命令：

```bash
systemctl status qqbot
journalctl -u qqbot -f
systemctl restart qqbot
systemctl stop qqbot
bash status.sh
```

## 常用命令

| 类别 | 示例 |
| --- | --- |
| 抽卡 | `单抽`、`十连`、`限定十连`、`十抽跳过` |
| 资产 | `获取呱太`、`签到`、`个人记录`、`兑换呱太`、`红抽`、`蓝抽` |
| 队伍 | `队伍`、`队伍 我的卡`、`队伍 自动配队`、`队伍 切换 1` |
| 战斗 | `战斗`、`对战`、`BOSS战`、`战斗日志`、`战斗GIF` |
| 竞技 | `排行榜`、`抽卡排行`、`挑战 1` |
| 帮助 | `帮助`、`help` |

队伍设置、筛选和翻页命令较多，请在 Bot 内发送 `帮助` 查看当前版本的完整说明。

## 目录结构

```text
ifbot/
├── qq_bot_ws.py          # QQ 官方 WebSocket 主入口
├── battle_system.py      # 战斗引擎
├── gif_renderer.py       # 战斗 GIF 渲染
├── team_system.py        # 队伍与预设
├── ranking.py            # 排行榜与竞技
├── rescue_event.py       # Raid/救援活动
├── json_store.py          # 并发安全的 JSON 存储
├── storage_maintenance.py # 日志轮转与存储清理
├── 卡牌信息.xlsx          # 抽卡卡池数据
├── cards_completed.xlsx  # 战斗数值
├── iconimage/             # 角色卡图
├── level/                 # 盲盒、边框和背景资源
├── state_icon/            # 战斗状态图标
├── config.example.py      # 可公开配置模板
├── requirements.txt       # Python 依赖
├── info/                  # 本地玩家存档，不入库
└── backup/                # 本地存档备份，不入库
```

## 更新日志

### 2026-09-02

- 增加线程安全的 JSON 存储层，支持原子写入、按用户锁定和并发读改写
- 为战斗引擎增加并发保护，避免多场战斗相互污染状态
- 增加共享图片缓存、日志轮转和运行时存储清理
- 改进战斗系统、GIF 渲染、队伍、排行榜和多平台入口
- 补充缺失的队伍 UI 资源和根目录依赖清单
- 优化固定图床与 Cloudflare Quick Tunnel 部署流程
- 将玩家存档、备份、真实配置和本地工作记录排除出公开仓库
- 重写 README，补充新机器部署、存档迁移和安全说明

### v0.0.3.2 (2026-07-05)

- 将卡牌图像、盲盒、排行榜等逻辑从主程序拆分为独立模块
- 新增 Raid/救援活动系统
- 改进战斗、GIF 和队伍模块的组织与集成
- 修复图片服务不可用时的地址处理问题

### v0.0.3.1 (2026-06-23)

- 改进 QQ Bot 长时间运行稳定性与图片服务部署
- 增加每日自动备份
- 支持取消抽卡并返还呱太
- 增加“我的卡”筛选，改进配队体验
- 上线排行榜奖励、CDKEY 和三星卡兑换碎片功能
- 持续修复战斗引擎和 GIF 渲染问题

### v0.0.3 (2026-06-18)

- 迁移到 QQ 官方 Bot API
- 新增 WebSocket 运行方式
- 进一步改进 GIF 战斗回放的 game loop 模拟

### v0.0.22 (2026-06-16)

- 增加 KOOK Bot 入口
- 开始使用服务器后台部署

### v0.0.21 (2026-06-15)

- 新增战斗 GIF 实时生成
- 建立完整战斗回合与画面帧生成流程

### v0.0.2 (2026-06-13)

- 重构战斗系统，实现 6 种属性、21 种 Buff 词条和多种状态效果
- 修复排行榜与自动配队
- 增加多队伍槽位和管理员命令
- 压缩输出图片，降低网络传输开销

### v0.0.15 (2026-06-12)

- 增加 PVE/PVP 自动战斗
- 改进排行榜和自动配队

### v0.0.14 (2026-06-11)

- 增加消息发送限速
- 增加日活统计和敏感词过滤

### v0.0.13 (2026-06-11)

- 修复初期版本问题

### v0.0.12 (2026-06-10)

- 新增三星专属池
- 显示当前可抽取次数

### v0.0.11 (2026-06-10)

- 新增配队系统
- 支持使用序号选卡和自动识别卡牌类型

### v0.0.1 (2026-06-10)

- 新增三星卡收藏分页和重复数量标记
- 统一背景图处理，增加抽卡详细信息

### v0.0.05 (2026-06-09)

- 新增“十抽跳过”和“三王女”命令

### v0.0.03 (2026-06-09)

- 新增碎片、个人记录和排行榜系统

### v0.0.02 (2026-06-09)

- 将保底调整为 FES 限定三星保底
- 增加三星概率分配、十连保底和 FES 统计

### v0.0.01 (2026-06-09)

- 发布首个版本
- 实现单抽、十连、呱太、保底和卡面合成

## License

本项目使用 [Apache License 2.0](LICENSE)。
