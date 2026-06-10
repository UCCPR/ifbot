# 自动抽卡QQ Bot 搭建指南

> 本指南面向新手，逐步教你怎么搭建基于Napcat的自动抽卡机器人。

---

## 目录

1. [原理说明](#原理说明)
2. [准备工作](#准备工作)
3. [步骤一：安装Python依赖](#步骤一安装python依赖)
4. [步骤二：配置Napcat](#步骤二配置napcat)
5. [步骤三：启动Bot](#步骤三启动bot)
6. [步骤四：测试](#步骤四测试)
7. [常见问题](#常见问题)

---

## 原理说明

```
┌─────────┐    消息    ┌─────────┐    HTTP POST    ┌─────────────┐
│   QQ    │ ────────> │ Napcat  │ ──────────────> │ gacha_bot.py│
│  用户   │ <───────  │ (本地)  │ <────────────── │  (HTTP服务) │
└─────────┘   回复图片  └─────────┘    返回抽卡图片     └─────────────┘
```

- **Napcat**：相当于QQ的"中间人"，接收QQ消息后转发给我们的程序
- **gacha_bot.py**：Python写的HTTP服务，接收消息、处理抽卡、返回图片

---

## 准备工作

1. **Napcat 已安装并运行**
   - 下载地址：https://github.com/Naplab/Napcat
   - 需要配置好你的QQ机器人账号

2. **Python 3.8+ 已安装**
   - 检查：`python --version`

3. **项目文件已准备**
   ```
   zmdbot/
   ├── gacha_bot.py      # 抽卡程序
   ├── iconimage/        # 角色图标
   ├── level/            # 星级框和背景
   ├── 卡牌信息.xlsx     # 角色数据
   ├── info/             # 日志目录
   └── output/          # 输出图片目录
   ```

---

## 步骤一：安装Python依赖

打开命令行（CMD或PowerShell），输入：

```bash
pip install flask pillow openpyxl
```

验证安装成功：
```bash
python -c "from flask import Flask; from PIL import Image; import openpyxl; print('全部依赖OK')"
```

---

## 步骤二：配置Napcat

### 2.1 找到Napcat配置文件

Napcat的配置文件通常是 `config.json` 或在Napcat目录下。

### 2.2 配置消息推送

在Napcat配置中添加webhook地址，指向我们的bot：

```json
{
  "http": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 3000,
    "post_urls": [
      "http://127.0.0.1:3000/"
    ]
  },
  "reverse_servers": [
    {
      "enabled": true,
      "host": "0.0.0.0",
      "port": 8080,
      "reverse_api_url": "http://127.0.0.1:3000/",
      "reverse_event_url": "http://127.0.0.1:3000/",
      "reverse_file_url": "http://127.0.0.1:3000/"
    }
  ]
}
```

### 2.3 关键配置说明

| 配置项 | 说明 |
|--------|------|
| `post_urls` | Napcat收到消息后会POST到这里 |
| `reverse_api_url` | 反向API地址 |
| `host` | 监听地址，0.0.0.0表示接受所有来源 |
| `port` | 端口号 |

> **注意**：gacha_bot.py 默认监听 `0.0.0.0:3000`，确保端口不冲突。

---

## 步骤三：启动Bot

### 3.1 启动抽卡服务

```bash
cd g:\Program Files\TRAEProjects\zmdbot
python gacha_bot.py
```

看到以下输出说明启动成功：
```
[INFO] ==================================================
[INFO] 自动抽卡Bot 启动中...
[INFO] 图标目录: g:\Program Files\TRAEProjects\zmdbot\iconimage
[INFO] 星级图片目录: g:\Program Files\TRAEProjects\zmdbot\level
[INFO] Excel文件: g:\Program Files\TRAEProjects\zmdbot\卡牌信息.xlsx
[INFO] ==================================================
[INFO] 共加载 XXX 个角色
```

### 3.2 启动Napcat

按照Napcat文档启动Napcat，确保它连接到了QQ。

---

## 步骤四：测试

### 4.1 在QQ中发送命令

| 命令 | 说明 |
|------|------|
| `/单抽` | 抽取一张卡 |
| `/十连` | 抽取十张卡 |
| `/帮助` | 显示帮助信息 |

### 4.2 查看日志

日志文件位置：`info/gacha_info.log`

打开查看：
```bash
notepad info\gacha_info.log
```

错误日志：`info/gacha_error.log`

### 4.3 查看输出图片

抽卡图片保存在 `output/` 目录。

---

## 常见问题

### Q1: 提示"无法加载角色数据"

**解决方法**：
1. 检查 `卡牌信息.xlsx` 文件是否存在
2. 检查 `iconimage/` 目录下是否有图片
3. 查看 `info/gacha_error.log` 的具体错误

### Q2: Napcat收不到消息

**解决方法**：
1. 确认Napcat的 `post_urls` 配置正确指向 `http://127.0.0.1:3000/`
2. 确认gacha_bot.py已启动并监听3000端口
3. 检查防火墙是否阻止了3000端口

### Q3: 返回的图片是空白或错误

**解决方法**：
1. 检查 `level/` 目录下的星级图片是否齐全
2. 查看 `info/gacha_error.log`
3. 可能是角色图标找不到，程序会自动跳过但会用占位图

### Q4: 端口被占用

如果3000端口被占用，修改 `gacha_bot.py` 中的端口：

```python
app.run(host="0.0.0.0", port=3001, debug=False)  # 改成3001
```

同时修改Napcat配置中的端口。

### Q5: 如何修改抽卡概率

编辑 `gacha_bot.py` 中的 `draw_cards` 函数：

```python
star_weights = {1: 70, 2: 25, 3: 5}  # 修改这里的数字
```

数字代表百分比，1星70%，2星25%，3星5%。

---

## 目录结构说明

```
zmdbot/
├── gacha_bot.py      # 主程序
├── iconimage/        # 角色图标（character_icon_xxx.png）
├── level/            # 星级框和背景
│   ├── gacha_tmb_00_00.png  # 1星背景
│   ├── gacha_tmb_00_01.png  # 1星框
│   ├── gacha_tmb_01_00.png  # 2星背景
│   ├── gacha_tmb_01_01.png  # 2星框
│   ├── gacha_tmb_02_00_b.png # 3星背景
│   └── gacha_tmb_02_01.png  # 3星框
├── 卡牌信息.xlsx     # 角色数据库
├── info/             # 日志目录（自动创建）
│   ├── gacha_info.log    # 正常日志
│   └── gacha_error.log    # 错误日志
└── output/          # 输出图片目录（自动创建）
```

---

## 下一步

- 想让Bot更智能？添加更多命令
- 想改抽卡动画？研究PIL图片合成
- 想接入数据库？用SQLite存储抽卡记录

祝玩得开心！
