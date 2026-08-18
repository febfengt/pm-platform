"""PM 私信平台 - 配置"""
import os

# 支持 Docker 环境变量注入
PLATFORM_BOT_TOKEN = os.environ.get("PM_TOKEN", "YOUR_TOKEN_HERE")

# 管理员 UID，逗号分隔多个
_ADMIN_RAW = os.environ.get("PM_ADMIN", "7743246793")
PLATFORM_ADMIN_IDS = [int(x.strip()) for x in _ADMIN_RAW.split(",") if x.strip()]

# 路径（Docker 映射用）
BASE_DIR = os.environ.get("PM_BASE_DIR", os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.environ.get("PM_REGISTRY", os.path.join(BASE_DIR, "bot_registry.json"))
DATA_DIR = os.environ.get("PM_DATA", os.path.join(BASE_DIR, "bot_data"))