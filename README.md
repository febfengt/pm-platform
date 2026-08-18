# PM 私信平台

Telegram 私信平台 —— 让每个 TG 用户都能拥有自己的私信机器人。

## 功能

- 🤖 **平台 Bot**：统一管理平台，支持注册/注销/查看子 bot
- 📬 **私信转发**：用户私信子 bot → 原样转发给你（文字/语音/图片/视频/文件）
- ✅ **人机验证**：新用户体验机器人验证按钮，点一次通过
- 🚫 **屏蔽/解封**：`/ban` `/unblock` 管理访问权限
- 🔒 **锁定回复**：点按钮或直接回复卡片，直接回复特定用户
- 👤 **双击查信息**：双击按钮显示用户名/UID/屏蔽状态
- 📋 **菜单命令**：输入 `/` 显示命令列表

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
├── platform_bot.py   # 平台 Bot（管理注册）
├── bot_manager.py    # 子 Bot 管理器（动态管理多个子 bot）
├── config.py         # 平台配置
├── storage/
│   ├── store.py      # 持久化存储（每个子 bot 独立）
│   ├── bot_registry.json  # 子 bot 注册表
│   └── __init__.py
├── bot_data/         # 各子 bot 的验证/屏蔽数据
└── logs/             # 运行日志
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

> 平台 bot 是你自己创建一个专门的 bot（通过 @BotFather），用来管理所有子 bot 的注册。

### 3. 启动

```bash
# 前台测试
python3 platform_bot.py

# 或 systemd
sudo systemctl enable --now pm-platform
```

## 数据持久化

- **子 bot 注册表**：`storage/bot_registry.json`
- **用户验证/屏蔽**：`bot_data/<bot_id>/*.json`（每个子 bot 独立）

重启后自动加载已注册的子 bot。

## 安全说明

- token 只存在本地，不上传到任何外部服务
- 每个子 bot 的数据完全隔离
- 平台 bot 只有管理员才能操作，其他用户无法访问