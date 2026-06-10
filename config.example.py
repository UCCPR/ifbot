# 配置文件示例
# 复制此文件为 config.py 并填写实际值

# Napcat配置
NAPCAT_HOST = "127.0.0.1"
NAPCAT_PORT = 3000  # Napcat HTTP API端口（http.port配置项）
NAPCAT_TOKEN = ""  # Napcat的access_token，留空则不使用

# Flask应用配置
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000  # Flask服务端口（避免与Napcat冲突）