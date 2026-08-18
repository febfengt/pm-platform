#!/usr/bin/env python3
"""平台 Bot - 管理子 bot 的注册/注销/列表"""
import asyncio, json, os
from aiogram import Bot, Dispatcher, F
from aiogram.types import BotCommand, MenuButtonCommands
from config import PLATFORM_BOT_TOKEN, PLATFORM_ADMIN_IDS
from bot_manager import (
    register_bot, unregister_bot, list_bots,
    load_saved_bots, start_all_bots,
)

logging = __import__("logging")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

bot = Bot(token=PLATFORM_BOT_TOKEN)
dp = Dispatcher()
_registering = {}  # uid -> admin_uid


@dp.message(F.chat.type == "private")
async def on_private(msg):
    uid = msg.from_user.id
    admins = PLATFORM_ADMIN_IDS

    # 处理注册流程(用户发token)
    if uid in _registering:
        admin_uid = _registering.pop(uid)
        token = msg.text.strip().replace(" ", "")
        try:
            mgr = await register_bot(token, admin_uid)
            asyncio.create_task(mgr.start())
            await msg.answer(
                "✅ 子bot注册成功！\n\n" +
                "Bot ID：" + str(mgr.bot_id) + "\n" +
                "用户名：@" + (mgr.bot.username or "?") + "\n\n" +
                "子bot已启动，功能：\n" +
                "• 私信验证(防机器人)\n" +
                "• 私信转发到你的账号\n" +
                "• /ban /unblock 屏蔽/解封\n" +
                "• /user 查看用户\n" +
                "• /lock 锁定回复\n" +
                "• /replyoff 取消锁定")
        except ValueError as e:
            await msg.answer("❌ " + str(e))
        except Exception as e:
            await msg.answer("❌ 注册失败: " + str(e))
        return

    if uid not in admins:
        return  # 非管理员不能注册平台bot

    text = msg.text or ""
    if text == "/start":
        await msg.answer(
            "🤖 PM 私信平台 Bot\n\n" +
            "功能：\n" +
            "/register - 注册新子bot\n" +
            "/list - 列出所有子bot\n" +
            "/unregister <id> - 注销子bot\n" +
            "/status - 平台状态")
    elif text == "/register":
        _registering[uid] = uid
        await msg.answer("请发送你的 bot token（从 @BotFather 获取）")
    elif text == "/list":
        bots = list_bots()
        if not bots:
            await msg.answer("📋 暂无已注册的子bot")
            return
        lines = ["📋 已注册的子bot（共 {} 个）:".format(len(bots))]
        for bid, mgr in bots.items():
            lines.append("• @{} (ID:{}) 管理员:{} 状态:运行中".format(
                mgr.name, bid, ",".join(str(a) for a in mgr.admins)))
        await msg.answer("\n".join(lines))
    elif text.startswith("/unregister "):
        bid = int(text.split()[1].strip())
        if await unregister_bot(bid):
            await msg.answer("✅ 子bot " + str(bid) + " 已注销")
        else:
            await msg.answer("❌ 找不到 id=" + str(bid))
    elif text == "/status":
        bots = list_bots()
        await msg.answer(
            "📊 平台状态:\n" +
            "子bot数量: {}\n" +
            "运行状态: 正常".format(len(bots)))
    else:
        return

    # 设置菜单
    try:
        await bot.set_chat_menu_button(MenuButtonCommands(), chat_id=msg.chat.id)
    except Exception:
        pass


async def main():
    logging.info("平台Bot 启动 ✓")
    commands = [
        ("register", "注册新子bot"),
        ("list", "列出所有子bot"),
        ("unregister", "注销子bot <bot_id>"),
        ("status", "平台状态"),
    ]
    try:
        await bot.set_my_commands(
            [BotCommand(command=c, description=d) for c, d in commands])
    except Exception:
        pass

    # 加载之前保存的子bot
    await load_saved_bots()
    # 后台启动所有子bot(非阻塞)
    for mgr in list_bots().values():
        asyncio.create_task(mgr.start())
        logging.info("后台启动子bot id={}".format(mgr.bot_id))
    logging.info("平台Bot 开始polling")

    # 平台bot主循环(阻塞)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())