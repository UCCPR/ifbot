# 配置文件示例
# 复制此文件为 config.py 并填写实际值

# Napcat配置
NAPCAT_HOST = "127.0.0.1"
NAPCAT_PORT = 3000  # Napcat HTTP API端口（http.port配置项）
NAPCAT_TOKEN = ""  # NapCatQQ的access_token（在Napcat的webui.json中查看），留空则不认证

# Flask应用配置
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000  # Flask服务端口（避免与Napcat冲突）

# ========== 抽卡概率配置 ==========

# 保底配置
PITY_LIMIT = 150  # 多少抽必出フェス限定三星

# 呱太配置
GACHA_COST = 300        # 单抽价格（呱太）
GACHA10_COST = 3000     # 十连价格（呱太）
GACHA10_COOLDOWN_SECONDS = 60  # 十连冷却时间（秒），每个用户一分钟至多抽一次十连
GET_GACHA_COOLDOWN_SECONDS = 60  # 获取呱太冷却时间（秒）
LIMITED_GACHA_COST = 15000  # 限定池十连价格（呱太）
LIMITED_GACHA_COOLDOWN_SECONDS = 480  # 限定池冷却时间（秒），8分钟
GET_GACHA_REWARD = 10000  # 获取呱太奖励
DAILY_REWARD = 30000     # 每日签到奖励（呱太）

# 盲盒开箱配置
MYSTERY_BOX_CHANCE = 0.02  # 黑色盲盒概率（2%）
MUTATION_NO_CHANGE = 0.88  # 不突变概率（88%）
MUTATION_1_TO_2 = 0.08    # 1星→2星概率（8%）
MUTATION_1_TO_3 = 0.02    # 1星→3星概率（2%）
MUTATION_2_TO_3 = 0.05    # 2星→3星概率（5%）
BOX_OPEN_TIMEOUT = 300     # 盲盒开启超时时间（秒）

# 三星池子配置
THREE_STAR_POOL_RED_COST = 1500   # 红色碎片消耗（1星卡转化）
THREE_STAR_POOL_BLUE_COST = 350   # 蓝色碎片消耗（2星卡转化）

# 抽卡概率（三星内部分配）
FES_LIMIT_PROB = 0.25     # フェス限定概率（25%）
PERIOD_LIMIT_PROB = 0.35  # 期間限定概率（35%）
OTHER_3STAR_PROB = 0.40   # 其他三星概率（40%）

# 盲盒星级概率（权重）
MYSTERY_BOX_2STAR_PROB = 65  # 黑色盲盒2星概率
MYSTERY_BOX_3STAR_PROB = 35  # 黑色盲盒3星概率
NORMAL_BOX_1STAR_PROB = 72   # 正常盲盒1星概率
NORMAL_BOX_2STAR_PROB = 23   # 正常盲盒2星概率
NORMAL_BOX_3STAR_PROB = 3    # 正常盲盒3星概率

# 抽卡星级概率（呱太抽卡）
GACHA_1STAR_PROB = 72   # 1星概率（权重）
GACHA_2STAR_PROB = 23   # 2星概率（权重）
GACHA_3STAR_PROB = 3    # 3星概率（权重）

# 管理员配置
ADMIN_QQ = "3590876913"  # 管理员QQ号，可使用管理命令

# BOSS战配置
BOSS_CARD_ID = "100430006"  # BOSS战使用的卡牌ID（3星B卡）
BOSS_BATTLE_COOLDOWN_SECONDS = 60  # BOSS战冷却时间（秒）

# 额外配置示例（自定义添加）
DEBUG_MODE = False  # 是否开启调试模式
LOG_LEVEL = "INFO"  # 日志级别：DEBUG, INFO, WARNING, ERROR