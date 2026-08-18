FROM python:3.11-slim

LABEL org.opencontainers.image.source=https://github.com/febfengt/pm-platform

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && pip install "aiogram>=3.30" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制代码
COPY platform_bot.py config.py ./

# 确保数据目录
RUN mkdir -p /data/bot_data

# 默认环境变量
ENV PM_TOKEN="" \
    PM_ADMIN="7743246793" \
    PM_REGISTRY="/data/bot_registry.json" \
    PM_DATA="/data/bot_data"

CMD ["python3", "platform_bot.py"]