# PM 私信平台

Telegram 私信平台 —— 让每个 TG 用户都能拥有自己的私信机器人。

## 功能

- **平台 Bot**：统一管理平台，支持注册/注销/查看子 bot
- **私信转发**：用户私信子 bot → 原样转发给你（文字/语音/图片/视频/文件/表情包）
- **人机验证**：新用户点一次按钮通过验证
- **屏蔽/解封**：`/ban` `/unblock` 管理访问权限
- **锁定回复**：点按钮或直接回复卡片锁定用户
- **双击查信息**：双击按钮显示用户名/UID/屏蔽状态
- **持久化**：重启后自动恢复所有子 bot

## 用户流程

1. 去 [@BotFather](https://t.me/BotFather) 创建自己的 bot，拿到 token
2. 给平台 bot 发 `/register`，然后发送你的 bot token
3. 子 bot 立刻上线，功能完整可用

## 管理员命令（平台 Bot）

| 命令 | 说明 |
|---|---|
| `/register` | 注册新子 bot（下一步发 token）|
| `/list` | 列出所有已注册子 bot |
| `/unregister <id>` | 注销指定子 bot |
| `/status` | 查看平台状态 |

## 管理员命令（子 Bot）

| 命令 | 说明 |
|---|---|
| `/ban <uid>` | 屏蔽用户 |
| `/unblock <uid>` | 解除屏蔽 |
| `/user <uid>` | 查看用户信息 |
| `/lock <uid>` | 锁定回复到指定用户 |
| `/replyoff` | 取消回复锁定 |
| `/help` | 显示命令帮助 |

## 文件结构

```
pm_platform/
├── platform_bot.py    # 平台 + 所有子 bot 核心逻辑（单文件）
├── config.py          # 配置
├── bot_registry.json  # 子 bot 注册表（自动生成）
└── bot_data/          # 各子 bot 的验证/屏蔽/锁定数据（自动生成）
```

## 部署

### 1. 安装依赖

```bash
pip3 install --break-system-packages aiogram
```

### 2. 配置

编辑 `config.py`：

```python
PLATFORM_BOT_TOKEN = "你的平台bot的token"
PLATFORM_ADMIN_IDS = [你的Telegram UID]
```

> 平台 bot 通过 @BotFather 创建，用来管理所有子 bot 的注册。

### 3. 启动

```bash
# 前台测试
python3 platform_bot.py

# 或 systemd（见 pm-platform.service）
sudo systemctl enable --now pm-platform
```

## systemd 服务

```ini
[Unit]
Description=PM 私信平台
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/pm_platform
ExecStart=/usr/bin/python3 /root/pm_platform/platform_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 安全说明

- token 只存在本地，不上传任何外部服务
- 每个子 bot 的数据完全隔离
- 平台 bot 只有管理员才能操作，其他用户无法访问