"""PM 私信平台 - 配置"""
import os

# 平台bot的token
PLATFORM_BOT_TOKEN = "YOUR_TOKEN_HERE"

# 平台管理员
PLATFORM_ADMIN_IDS = [7743246793]

# 路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(BASE_DIR, "bot_registry.json")
DATA_DIR = os.path.join(BASE_DIR, "bot_data")