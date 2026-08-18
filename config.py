"""PM 私信平台 - 配置"""
import os

# 读取 .env 文件（如果存在）
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# 平台 Bot Token
PLATFORM_BOT_TOKEN = os.environ.get("PM_TOKEN", "").strip() or "YOUR_TOKEN_HERE"

# 管理员 UID，逗号分隔多个
_ADMIN_RAW = os.environ.get("PM_ADMIN", "7743246793")
PLATFORM_ADMIN_IDS = [int(x.strip()) for x in _ADMIN_RAW.split(",") if x.strip()]

# 路径
BASE_DIR = os.environ.get("PM_BASE_DIR", os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.environ.get("PM_REGISTRY", os.path.join(BASE_DIR, "bot_registry.json"))
DATA_DIR = os.environ.get("PM_DATA", os.path.join(BASE_DIR, "bot_data"))