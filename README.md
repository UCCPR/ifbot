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
## 文件说明

| 文件 | 用途 | 建议 |
| --- | --- | --- |
| `qq_bot_ws.py` | QQ 官方 Bot WebSocket 版 | 当前主入口 |
| `qq_bot.py` | QQ 官方回调版 | 兼容入口 |
| `gacha_bot.py` | NapCat/OneBot 版 | 旧部署兼容 |
| `kook_bot.py` | KOOK 版 | 独立配置 |

以下部署说明默认使用 `qq_bot_ws.py`。

## 如何食用

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

### v0.0.01 (2026-06-09)
- 初始版本发布
- 实现基础抽卡功能（单抽、十连）
- 支持角色图、框、背景图合成
- 添加呱太系统
- 添加保底机制
- 稍稍能用了

### v0.0.02 (2026-06-09)
- 修改保底为FES限定三星保底
- 实现三星概率分配
- 添加十连保底
- 添加FES统计功能

### v0.0.03 (2026-06-09)
- 添加碎片系统
- 添加个人记录查询
- 添加排行榜功能

### v0.0.05 (2026-06-09)
- 添加"十抽跳过"命令
- 添加"三王女"特殊命令

### v0.0.1 (2026-06-10)
- 实现三星卡收藏分页显示
- 重复三星卡显示计数标记
- 统一背景图处理方式
- 添加详细信息查询命令

### v0.0.11 (2026-06-10)
- 新增配队系统
	- 使用序号选择卡牌加入队伍
	- 自动识别卡类型

### v0.0.12 (2026-06-10)
- 新增三星only
- 显示可抽取次数

### v0.0.13 (2026-06-11)
- 修bug

### v0.0.14 (2026-06-11)
- 控制消息发送速率
- 增加日活数据，可以在后台看到
- 添加敏感词过滤能力

### v0.0.15 (2026-06-12)
- 增加自动对战系统，支持PVE和PVP
- 修改排行榜系统
- 自动配队

### v0.0.2 ！ (2026-06-13)
- 重构战斗系统，复刻了if6种属性、具有21个不同buff词条、多种状态效果的复杂战斗系统
- 修复排行榜系统
- 修复自动配队
- 增加了队伍的槽位，可以自由切换
- 大大压缩图片，降低网络耗费
- 添加管理员命令
- 热修复，修了巨多bug

### v0.0.21 (2026-06-15)
- 增加战斗GIF实时生成功能，待完善
- 修了一整天BUG，发现大大低估了这个功能的实现难度
- 这真的要模拟出一整个gameloop
- 吓哭了

### v0.0.22 (2026-06-16)
- 移植到了Kook！
- 后台转到了服务器
- 玩玩Kook的BOT
- 还是官方支持的bot好

## v0.0.3!(2026-06-18)
- QQ官方bot突然复活了
- 不说啥了，立刻移植
- 使用websocket
- GIF生成器进一步改进，真正实现了模拟gameloop的目标
- ifbot堂堂复活！

## v0.0.3.1!(2026-06-23)
- 这几天都在处理QQBOT稳定性的问题
- 搭了一个稳定图床，甚至为了它买了一个域名
- 反复崩溃真难受呀，还好总算摸索出一套稳定24h运行bot的方法
- 为了保护数据加入了自动备份功能
- 抽卡可以取消，返还呱太，改进体验
- 新增我的卡筛选功能，配队便利化
- 排行榜的奖励系统上线
- 新增CDK系统
- 新增三星卡兑换碎片功能
- 战斗系统和GIF生成依然有很多问题，这也是这段时间主要的工作方向

## License

本项目使用 [Apache License 2.0](LICENSE)。
