# 配置文件示例
# 复制此文件为 config.py 并填写实际值

# Napcat配置
NAPCAT_HOST = "127.0.0.1"
NAPCAT_PORT = 3000  # Napcat HTTP API端口（http.port配置项）
NAPCAT_TOKEN = ""  # Napcat的access_token，留空则不使用

# Flask应用配置
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000  # Flask服务端口（避免与Napcat冲突）

# ========== 抽卡概率配置 ==========

# 保底配置
PITY_LIMIT = 150  # 多少抽必出フェス限定三星

# 呱太配置
GACHA_COST = 300        # 单抽价格（呱太）
GACHA10_COST = 3000     # 十连价格（呱太）
GET_GACHA_REWARD = 10000  # 获取呱太奖励
DAILY_REWARD = 30000     # 每日签到奖励（呱太）

# 盲盒开箱配置
MYSTERY_BOX_CHANCE = 0.5  # 黑色盲盒概率
MUTATION_NO_CHANGE = 0.5  # 不突变概率
MUTATION_1_TO_2 = 0.5    # 1星→2星概率
MUTATION_1_TO_3 = 0.5    # 1星→3星概率
MUTATION_2_TO_3 = 0.5    # 2星→3星概率
BOX_OPEN_TIMEOUT = 300     # 盲盒开启超时时间（秒）

# 三星池子配置
THREE_STAR_POOL_RED_COST = 1500   # 红色碎片消耗
THREE_STAR_POOL_BLUE_COST = 350   # 蓝色碎片消耗

# 抽卡概率（三星内部分配）
FES_LIMIT_PROB = 0.5     # フェス限定概率
PERIOD_LIMIT_PROB = 0.5  # 期間限定概率
OTHER_3STAR_PROB = 0.5   # 其他三星概率

# 盲盒星级概率（权重）
MYSTERY_BOX_2STAR_PROB = 0.5  # 黑色盲盒2星概率
MYSTERY_BOX_3STAR_PROB = 0.5  # 黑色盲盒3星概率
NORMAL_BOX_1STAR_PROB = 0.5   # 正常盲盒1星概率
NORMAL_BOX_2STAR_PROB = 0.5   # 正常盲盒2星概率
NORMAL_BOX_3STAR_PROB = 0.5   # 正常盲盒3星概率

# 额外配置示例（自定义添加）
DEBUG_MODE = False  # 是否开启调试模式
LOG_LEVEL = "INFO"  # 日志级别：DEBUG, INFO, WARNING, ERROR