"""统一Bot平台 - 简化重写版"""
import asyncio
import json
import os
import threading
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, InlineKeyboardMarkup, InlineKeyboardButton,
    MenuButtonCommands,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# 配置
from config import PLATFORM_BOT_TOKEN, PLATFORM_ADMIN_IDS, BASE_DIR, REGISTRY_PATH, DATA_DIR


# ========== 持久化 ==========
_data_lock = threading.Lock()


def _bot_data(bot_id, name):
    d = os.path.join(DATA_DIR, str(bot_id))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name + ".json")
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            return {}
    return {}


def _save(bot_id, name, data):
    d = os.path.join(DATA_DIR, str(bot_id))
    os.makedirs(d, exist_ok=True)
    with _data_lock:
        json.dump(data, open(os.path.join(d, name + ".json"), "w"), ensure_ascii=False)


def is_verified(bot_id, uid): return uid in _bot_data(bot_id, "verified")
def set_verified(bot_id, uid, v):
    d = _bot_data(bot_id, "verified"); d[str(uid)] = v; _save(bot_id, "verified", d)


def is_blocked(bot_id, uid):
    return _bot_data(bot_id, "blocked").get(str(uid), False)


def set_blocked(bot_id, uid, b):
    d = _bot_data(bot_id, "blocked"); d[str(uid)] = b; _save(bot_id, "blocked", d)


# ========== 子Bot实例 ==========
_current_reply = {}  # bot_id -> {admin_chat: uid}
_last_tap = {}
_verify_times = {}  # bot_id -> {uid: verify_hour}
_bot_registry = {}   # bot_id -> {name, admins, token, bot, dp, tasks}


def _extract_uid(reply_msg):
    """从被回复消息提取UID(文本或按钮)"""
    if not reply_msg:
        return None
    # 文本
    for part in (reply_msg.text or "").split():
        if part.isdigit() and len(part) > 5:
            return int(part)
    # 按钮
    if reply_msg.reply_markup:
        try:
            for row in reply_msg.reply_markup.inline_keyboard or []:
                for btn in row:
                    if btn.callback_data and btn.callback_data.startswith("reply_"):
                        return int(btn.callback_data.split("_", 1)[1])
        except Exception:
            pass
    return None


async def _reply_to_user(bot_id, bot, admin_chat, uid, msg):
    """代发管理员消息"""
    try:
        if msg.voice:
            await bot.send_voice(uid, msg.voice.file_id)
        elif msg.photo:
            await bot.copy_message(uid, admin_chat, msg.message_id, caption=msg.caption or "")
        elif msg.video:
            await bot.copy_message(uid, admin_chat, msg.message_id, caption=msg.caption or "")
        elif msg.document or msg.animation:
            await bot.copy_message(uid, admin_chat, msg.message_id)
        elif msg.sticker:
            await bot.send_sticker(uid, msg.sticker.file_id)
        elif msg.text:
            await bot.send_message(uid, msg.text, parse_mode="HTML")
        else:
            return False
        return True
    except Exception as e:
        logging.error("代发失败 uid={} bot={}: {}".format(uid, bot_id, e))
        return True


def _user_label(user):
    return "@" + user.username if user.username else str(user.id)


async def _forward_to_admin(bot_id, bot, msg):
    """转发用户私信到管理员"""
    admins = _bot_registry[bot_id]["admins"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=_user_label(msg.from_user), callback_data="reply_" + str(msg.from_user.id))]])
    for admin in admins:
        try:
            if msg.voice:
                await bot.send_voice(admin, msg.voice.file_id, reply_markup=kb)
            elif msg.photo or msg.video or msg.document or msg.animation:
                await bot.copy_message(admin, msg.chat.id, msg.message_id,
                                       caption=msg.caption or "", reply_markup=kb)
            elif msg.sticker:
                await bot.send_sticker(admin, msg.sticker.file_id, reply_markup=kb)
            else:
                safe = (msg.text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                await bot.send_message(admin, safe, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logging.error("转发失败 admin={} bot={}: {}".format(admin, bot_id, e))


async def _issue_verify(bot_id, bot, msg):
    import datetime as _dt
    h = _dt.datetime.now().hour
    vt = _verify_times.setdefault(bot_id, {})
    vt[str(msg.from_user.id)] = h
    await msg.answer("👋 你好！请先通过人机验证。\n🕐 当前时间(24小时制)是 **{}点**。请回复正确的整点时间。".format(h), parse_mode="HTML")


async def _handle_admin_cmd(bot_id, bot, msg):
    text = msg.text or ""
    chat_id = str(msg.chat.id)
    cur_uid = _current_reply.get(bot_id, {}).get(chat_id)

    if text == "/start":
        await msg.answer("🤖 你的私信Bot已就绪！\n\n发送 /help 查看命令列表。")
        return

    def _reply(s): bot.send_message(chat_id, s)

    if text.startswith(("/ban ", "/block ")):
        set_blocked(bot_id, int(text.split()[1].strip()), True); await msg.answer("🚫 已屏蔽")
    elif text in ("/ban", "/block"):
        if not cur_uid: await _reply("⚠️ 未锁定, 用 /ban <UID>")
        else: set_blocked(bot_id, cur_uid, True); await msg.answer("🚫 已屏蔽 " + str(cur_uid))
    elif text.startswith("/unblock "):
        set_blocked(bot_id, int(text.split()[1].strip()), False); await msg.answer("✅ 已解除屏蔽")
    elif text == "/unblock":
        if not cur_uid: await _reply("⚠️ 未锁定, 用 /unblock <UID>")
        else: set_blocked(bot_id, cur_uid, False); await msg.answer("✅ 已解除 " + str(cur_uid))
    elif text.startswith("/user "):
        await _user_info(bot_id, bot, msg, int(text.split()[1].strip()))
    elif text == "/user":
        if not cur_uid: await _reply("⚠️ 未锁定, 用 /user <UID>")
        else: await _user_info(bot_id, bot, msg, cur_uid)
    elif text.startswith("/lock "):
        _current_reply.setdefault(bot_id, {})[chat_id] = int(text.split()[1].strip())
        await msg.answer("🔒 已锁定")
    elif text == "/replyoff":
        _current_reply.setdefault(bot_id, {}).pop(chat_id, None)
        await msg.answer("🔒 已取消回复锁定")
    elif text in ("/help", "/list"):
        await msg.answer("📋 /ban <uid> /unblock <uid> /user <uid> /lock <uid> /replyoff")


async def _user_info(bot_id, bot, msg, uid):
    try:
        user = await bot.get_chat(uid)
    except Exception:
        user = None
    await msg.answer(
        "用户：" + ("@" + user.username if user and user.username else "无") +
        "\nUID：" + str(uid) +
        "\n" + ("已被屏蔽" if is_blocked(bot_id, uid) else "未被屏蔽"))


async def _handle_private(bot_id, bot, msg):
    uid = msg.from_user.id
    admins = _bot_registry[bot_id]["admins"]

    if uid in admins:
        # 回复处理
        text = msg.text or ""
        if not text.startswith("/"):
            chat_id = str(msg.chat.id)
            replies = _current_reply.get(bot_id, {})
            target = replies.get(chat_id)
            if msg.reply_to_message and not target:
                uid2 = _extract_uid(msg.reply_to_message)
                if uid2:
                    target = uid2; replies[chat_id] = uid2
                    _current_reply[bot_id] = replies
            if target:
                if await _reply_to_user(bot_id, bot, chat_id, target, msg):
                    return
        return await _handle_admin_cmd(bot_id, bot, msg)

    if is_blocked(bot_id, uid):
        return await msg.answer("🚫 你已被屏蔽，无法发送私信。")
    if not is_verified(bot_id, uid):
        uid_str = str(uid)
        vt = _verify_times.get(bot_id, {})
        verify_hour = vt.get(uid_str)
        if verify_hour is None:
            await _issue_verify(bot_id, bot, msg)
            return
        if msg.text:
            txt = msg.text.strip()
            is_correct = (txt == str(verify_hour) or
                          str(verify_hour).zfill(2) == txt or
                          str(verify_hour) + "点" in txt or
                          str(verify_hour).zfill(2) + "点" in txt or
                          str(verify_hour) + ":00" in txt or
                          str(verify_hour).zfill(2) + ":00" in txt)
            if is_correct:
                set_verified(bot_id, uid, True)
                vt.pop(uid_str, None)
                await msg.answer("✅ 验证通过！你可以开始发送私信了。")
                return
        await _issue_verify(bot_id, bot, msg)
        return
    if (msg.text or "").strip() == "/start":
        return
    await _forward_to_admin(bot_id, bot, msg)


async def _handle_callback(bot_id, bot, cb):
    admins = _bot_registry[bot_id]["admins"]
    if cb.from_user.id not in admins:
        await cb.answer(); return
    try: await cb.answer()
    except Exception: pass

    data = cb.data
    if not data.startswith("reply_"):
        return

    uid = int(data.split("_", 1)[1])
    user = await bot.get_chat(uid)
    name = user.username or str(user.id)
    chat_id = str(cb.message.chat.id)

    now = __import__("time").time()
    taps = _last_tap.setdefault(bot_id, {})
    replies = _current_reply.setdefault(bot_id, {})
    prev = taps.get(chat_id)

    if prev and prev[0] == uid and now - prev[1] < 3:
        taps.pop(chat_id, None)
        try:
            await cb.message.answer(
                "用户：" + name + "\nUID：" + str(uid) +
                "\n" + ("已被屏蔽" if is_blocked(bot_id, uid) else "未被屏蔽"))
        except Exception:
            pass
        return

    taps[chat_id] = (uid, now)
    replies[chat_id] = uid
    try:
        await cb.message.answer(
            "🔒 已锁定回复(UID " + str(uid) + "), 再点跳用户, /replyoff 解锁")
    except Exception:
        pass


def make_bot(bot_id, token, admins, name=""):
    """创建并注册一个子bot"""
    bot = Bot(token=token)
    dp = Dispatcher()

    @dp.message(F.chat.type == "private")
    async def on_msg(msg):
        await _handle_private(bot_id, bot, msg)

    @dp.callback_query(lambda c: True)
    async def on_cb(cb):
        await _handle_callback(bot_id, bot, cb)

    _bot_registry[bot_id] = {
        "name": name, "admins": admins, "token": token,
        "bot": bot, "dp": dp, "tasks": [],
    }
    _current_reply[bot_id] = _current_reply.get(bot_id, {})
    _last_tap[bot_id] = _last_tap.get(bot_id, {})
    return _bot_registry[bot_id]


# ========== 平台Bot ==========
_bot = Bot(token=PLATFORM_BOT_TOKEN) if PLATFORM_BOT_TOKEN else None
_dp = Dispatcher()
_registering = {}


@_dp.message(F.chat.type == "private")
async def on_platform_private(msg):
    uid = msg.from_user.id

    if uid in _registering:
        admin_uid = _registering.pop(uid)
        token = msg.text.strip().replace(" ", "")
        try:
            await register_bot(token, admin_uid)
            await msg.answer("✅ 子bot注册成功！Bot 已启动。\n命令: /list /unregister <id>")
        except ValueError as e:
            await msg.answer("❌ " + str(e))
        except Exception as e:
            await msg.answer("❌ 注册失败: " + str(e))
        return

    if uid not in PLATFORM_ADMIN_IDS:
        return

    text = msg.text or ""
    if text == "/start":
        await msg.answer("🤖 PM 私信平台\n\n/register - 注册新子bot\n/list - 列出所有子bot\n/unregister <id> - 注销\n/status - 平台状态")
    elif text == "/register":
        _registering[uid] = uid
        await msg.answer("请发送你的 bot token（从 @BotFather 获取）")
    elif text == "/list":
        if not _bot_registry:
            await msg.answer("📋 暂无已注册的子bot")
            return
        lines = ["📋 已注册（共 {} 个）:".format(len(_bot_registry))]
        for bid, info in _bot_registry.items():
            lines.append("• ID:{} @{} 管理员:{}".format(bid, info["name"], ",".join(str(a) for a in info["admins"])))
        await msg.answer("\n".join(lines))
    elif text.startswith("/unregister "):
        bid = int(text.split()[1].strip())
        if await unregister_bot(bid):
            await msg.answer("✅ 子bot " + str(bid) + " 已注销")
        else:
            await msg.answer("❌ 找不到 id=" + str(bid))
    elif text == "/status":
        await msg.answer("📊 平台状态: 子bot {} 个, 运行正常".format(len(_bot_registry)))

    try:
        await _bot.set_chat_menu_button(MenuButtonCommands(), chat_id=msg.chat.id)
    except Exception:
        pass


# ========== 注册/注销/持久化 ==========
async def register_bot(token, admin_uid):
    tmp_bot = Bot(token=token)
    me = await tmp_bot.get_me()
    bot_id = me.id
    if bot_id in _bot_registry:
        await tmp_bot.close()
        raise ValueError("bot已存在: " + str(bot_id))
    info = make_bot(bot_id, token, [admin_uid], me.username or "")
    info["tasks"].append(asyncio.create_task(_start_bot(bot_id)))
    _persist_registry()
    await tmp_bot.close()
    return info


async def _start_bot(bot_id):
    info = _bot_registry[bot_id]
    cmds = [
        ("ban", "屏蔽用户"), ("unblock", "解除屏蔽"),
        ("user", "查看用户信息"), ("lock", "锁定回复"),
        ("replyoff", "取消锁定"), ("help", "显示命令"),
    ]
    try:
        await info["bot"].set_my_commands([BotCommand(command=c, description=d) for c, d in cmds])
    except Exception:
        pass
    await info["dp"].start_polling(info["bot"])


async def unregister_bot(bot_id):
    info = _bot_registry.pop(bot_id, None)
    if not info:
        return False
    for t in info["tasks"]:
        t.cancel()
    try:
        await info["bot"].close()
    except Exception:
        pass
    _persist_registry()
    return True


def _persist_registry():
    data = {}
    for bid, info in _bot_registry.items():
        data[str(bid)] = {"name": info["name"], "admins": info["admins"], "token": info["token"]}
    json.dump(data, open(REGISTRY_PATH, "w"), ensure_ascii=False, indent=2)


def load_saved_bots():
    if not os.path.exists(REGISTRY_PATH):
        return
    try:
        data = json.load(open(REGISTRY_PATH))
    except Exception:
        return
    for bid_str, d in data.items():
        try:
            make_bot(int(bid_str), d["token"], d["admins"], d.get("name", ""))
        except Exception as e:
            logging.warning("加载bot {} 失败: {}".format(bid_str, e))


async def main():
    if not _bot:
        logging.error("PLATFORM_BOT_TOKEN 未设置!")
        return

    logging.info("平台Bot 启动 ✓")
    try:
        await _bot.set_my_commands([
            BotCommand("register", "注册新子bot"),
            BotCommand("list", "列出所有子bot"),
            BotCommand("unregister", "注销子bot <bot_id>"),
            BotCommand("status", "平台状态"),
        ])
    except Exception:
        pass

    load_saved_bots()
    for bid in list(_bot_registry.keys()):
        info = _bot_registry[bid]
        info["tasks"].append(asyncio.create_task(_start_bot(bid)))
        logging.info("后台启动子bot id={}".format(bid))

    logging.info("平台Bot 开始polling")
    try:
        await _dp.start_polling(_bot)
    except Exception:
        pass
    finally:
        logging.info("关闭所有子bot...")
        for info in _bot_registry.values():
            for t in info["tasks"]:
                t.cancel()
        logging.info("平台Bot 已退出")


if __name__ == "__main__":
    asyncio.run(main())