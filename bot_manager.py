#!/usr/bin/env python3
"""子bot管理器 - 动态管理多个子bot"""
import json, os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, InlineKeyboardMarkup, InlineKeyboardButton,
)
from storage.store import is_verified, set_verified, is_blocked, set_blocked
from config import PLATFORM_BOT

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# 所有子bot实例: bot_id -> Manager实例
_bot_managers = {}
_current_reply = {}  # bot_id -> {admin_chat -> uid}
_last_tap = {}       # bot_id -> {admin_chat -> (uid, ts)}


async def _reply_to_target(bot, admin_chat, uid, msg):
    """代发消息给目标用户(支持文字/语音/媒体)"""
    if msg.voice:
        await bot.send_voice(uid, msg.voice.file_id)
    elif msg.photo:
        await bot.copy_message(uid, admin_chat, msg.message_id, caption=msg.caption or "")
    elif msg.video:
        await bot.copy_message(uid, admin_chat, msg.message_id, caption=msg.caption or "")
    elif msg.document:
        await bot.copy_message(uid, admin_chat, msg.message_id)
    elif msg.animation:
        await bot.copy_message(uid, admin_chat, msg.message_id)
    elif msg.sticker:
        await bot.send_sticker(uid, msg.sticker.file_id)
    elif msg.text:
        await bot.send_message(uid, msg.text, parse_mode="HTML")
    else:
        return False
    return True


def _uid_from_card(text):
    for part in (text or "").split():
        if part.isdigit() and len(part) > 5:
            return int(part)
    return None


def _uid_from_button(reply_markup):
    if not reply_markup:
        return None
    try:
        for row in reply_markup.inline_keyboard or []:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("reply_"):
                    return int(btn.callback_data.split("_", 1)[1])
    except (AttributeError, KeyError):
        pass
    return None


async def _check_reply(bot_id, bot, msg):
    cid = str(msg.chat.id)
    replies = _current_reply.get(bot_id, {})
    target = replies.get(cid)
    if msg.reply_to_message and not target:
        uid = _uid_from_card(msg.reply_to_message.text or "") or _uid_from_button(
            msg.reply_to_message.reply_markup
        )
        if uid:
            target = uid
            replies[cid] = uid
    if not target:
        return False
    try:
        return await _reply_to_target(bot, msg.chat.id, target, msg)
    except Exception as e:
        logging.error("代发失败 uid={}: {}".format(target, e))
        return True


async def _forward_to_admin(bot_id, bot, msg):
    admins = _bot_managers[bot_id].admins
    u = msg.from_user
    label = "@" + u.username if u.username else str(u.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=label, callback_data="reply_" + str(u.id))]])
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
                await bot.send_message(admin, (msg.text or "").replace("&", "&amp;")
                                       .replace("<", "&lt;").replace(">", "&gt;"),
                                       reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logging.error("转发失败 admin {} bot {}: {}".format(admin, bot_id, e))


async def _admin_cmd(bot_id, bot, msg):
    text = msg.text or ""
    cid = str(msg.chat.id)
    replies = _current_reply.get(bot_id, {})
    cur_uid = replies.get(cid)
    b = bot_id

    if text.startswith(("/ban ", "/block ")):
        set_blocked(b, int(text.split()[1].strip()), True); await msg.answer("🚫 已屏蔽")
    elif text in ("/ban", "/block"):
        if not cur_uid: await msg.answer("⚠️ 未锁定, /ban <UID>"); return
        set_blocked(b, cur_uid, True); await msg.answer("🚫 已屏蔽 " + str(cur_uid))
    elif text.startswith("/unblock "):
        set_blocked(b, int(text.split()[1].strip()), False); await msg.answer("✅ 已解除屏蔽")
    elif text == "/unblock":
        if not cur_uid: await msg.answer("⚠️ 未锁定, /unblock <UID>"); return
        set_blocked(b, cur_uid, False); await msg.answer("✅ 已解除 " + str(cur_uid))
    elif text.startswith("/user "):
        uid = int(text.split()[1].strip())
        try:
            user = await bot.get_chat(uid)
        except Exception:
            user = None
        await msg.answer(
            "用户：" + ("@" + user.username if user and user.username else "无") +
            "\nUID：" + str(uid) +
            "\n" + ("已被屏蔽" if is_blocked(b, uid) else "未被屏蔽"))
    elif text == "/user":
        if not cur_uid: await msg.answer("⚠️ 未锁定, /user <UID>"); return
        try:
            user = await bot.get_chat(cur_uid)
        except Exception:
            user = None
        await msg.answer(
            "用户：" + ("@" + user.username if user and user.username else "无") +
            "\nUID：" + str(cur_uid) +
            "\n" + ("已被屏蔽" if is_blocked(b, cur_uid) else "未被屏蔽"))
    elif text == "/replyoff":
        replies.pop(cid, None); await msg.answer("🔒 已取消回复锁定")
    elif text.startswith("/lock "):
        replies[cid] = int(text.split()[1].strip()); await msg.answer("🔒 已锁定")
    elif text == "/list":
        await msg.answer("📋 /ban <uid> /unblock <uid> /user <uid> /lock <uid> /replyoff")
    elif text in ("/help", "/list"):
        await msg.answer("📋 /ban <uid> /unblock <uid> /user <uid> /lock <uid> /replyoff")


async def _issue_verify(bot_id, bot, msg):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ 我不是机器人")]], resize_keyboard=True)
    await msg.answer("👋 你好！请先通过人机验证。\n点击下方按钮即可通过：", reply_markup=kb)


async def _handle_private(bot_id, bot, msg):
    uid = msg.from_user.id
    admins = _bot_managers[bot_id].admins
    if uid in admins:
        if await _check_reply(bot_id, bot, msg): return
        return await _admin_cmd(bot_id, bot, msg)
    if is_blocked(bot_id, uid):
        return await msg.answer("🚫 你已被屏蔽,无法发送私信。")
    if not is_verified(bot_id, uid):
        if msg.text and "我不是机器人" in msg.text:
            set_verified(bot_id, uid, True)
            await msg.answer("✅ 验证通过！你可以开始发送私信了。")
        else:
            await _issue_verify(bot_id, bot, msg)
        return
    if (msg.text or "").strip() == "/start":
        return
    await _forward_to_admin(bot_id, bot, msg)


async def _handle_callback(bot_id, bot, cb):
    admins = _bot_managers[bot_id].admins
    if cb.from_user.id not in admins:
        await cb.answer(); return
    try:
        await cb.answer()
    except Exception:
        pass
    data = cb.data
    cid = str(cb.message.chat.id)
    if data.startswith("reply_"):
        uid = int(data.split("_", 1)[1])
        user = await bot.get_chat(uid)
        name = user.username or str(user.id)
        now = __import__("time").time()
        taps = _last_tap.get(bot_id, {})
        prev = taps.get(cid)
        replies = _current_reply.get(bot_id, {})
        if prev and prev[0] == uid and now - prev[1] < 3:
            _last_tap[bot_id] = taps
            _last_tap[bot_id].pop(cid, None)
            try:
                await cb.message.answer(
                    "用户：" + name + "\nUID：" + str(uid) +
                    "\n" + ("已被屏蔽" if is_blocked(bot_id, uid) else "未被屏蔽"))
            except Exception as e:
                logging.error("双点失败: {}".format(e))
            return
        _last_tap[bot_id] = taps
        _last_tap[bot_id][cid] = (uid, now)
        replies[cid] = uid
        _current_reply[bot_id] = replies
        try:
            await cb.message.answer(
                "🔒 已锁定回复(UID " + str(uid) + "), 再点跳用户, /replyoff 解锁")
        except Exception as e:
            logging.error("锁定回复失败: {}".format(e))


class BotManager:
    def __init__(self, bot_id: int, token: str, admins: list, name: str = ""):
        self.bot_id = bot_id
        self.token = token
        self.admins = admins
        self.name = name
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        _current_reply[bot_id] = _current_reply.get(bot_id, {})
        _last_tap[bot_id] = _last_tap.get(bot_id, {})
        self._register_handlers()

    def _register_handlers(self):
        @self.dp.message(F.chat.type == "private")
        async def on_private(msg):
            await _handle_private(self.bot_id, self.bot, msg)

        @self.dp.callback_query(lambda c: True)
        async def on_callback(cb):
            await _handle_callback(self.bot_id, self.bot, cb)

    async def start(self):
        await self._setup_commands()
        await self.dp.start_polling(self.bot)

    async def stop(self):
        await self.bot.close()

    async def _setup_commands(self):
        commands = [
            ("ban", "屏蔽用户"),
            ("unblock", "解除屏蔽"),
            ("user", "查看用户信息"),
            ("lock", "锁定回复"),
            ("replyoff", "取消锁定"),
            ("help", "显示命令"),
        ]
        try:
            from aiogram.types import BotCommand
            await self.bot.set_my_commands(
                [BotCommand(command=c, description=d) for c, d in commands])
        except Exception:
            pass

    def _json(self):
        return {"bot_id": self.bot_id, "name": self.name, "admins": self.admins,
                "token": self.token}

    @classmethod
    def from_json(cls, data: dict):
        return cls(data["bot_id"], data["token"], data["admins"], data.get("name", ""))


async def register_bot(token: str, admin_uid: int, name: str = "") -> BotManager:
    """注册新子bot"""
    bot = Bot(token=token)
    me = await bot.get_me()
    bot_id = me.id
    if bot_id in _bot_managers:
        raise ValueError("bot已存在: " + str(bot_id))
    manager = BotManager(bot_id, token, [admin_uid], name or me.username or "")
    _bot_managers[bot_id] = manager
    _persist_registry()
    logging.info("子bot注册成功 id={} @{}".format(bot_id, me.username or "?"))
    await bot.close()
    return manager


async def unregister_bot(bot_id: int) -> bool:
    """注销子bot"""
    mgr = _bot_managers.pop(bot_id, None)
    if not mgr:
        return False
    _persist_registry()
    logging.info("子bot注销 id={}".format(bot_id))
    return True


def list_bots():
    """列出所有已注册bot"""
    return _bot_managers


async def load_saved_bots() -> dict:
    """从本地加载已保存的bot注册信息"""
    mgrs = {}
    for mid, data in _load_registry().items():
        try:
            mgr = BotManager.from_json(data)
            mgrs[int(mid)] = mgr
            logging.info("加载子bot id={} @{}".format(mid, mgr.name))
        except Exception as e:
            logging.warning("加载子bot失败 id={}: {}".format(mid, e))
    _bot_managers.update(mgrs)
    return mgrs


async def start_all_bots():
    """启动所有已注册的子bot"""
    tasks = [mgr.start() for mgr in _bot_managers.values()]
    if tasks:
        import asyncio
        await asyncio.gather(*tasks)


# 持久化注册表
_REG_FILE = os.path.join(os.path.dirname(__file__), "..", "storage", "bot_registry.json")


def _load_registry():
    if not os.path.exists(_REG_FILE):
        return {}
    try:
        return json.load(open(_REG_FILE))
    except Exception:
        return {}


def _persist_registry():
    data = {}
    for mid, mgr in _bot_managers.items():
        data[str(mid)] = mgr._json()
    json.dump(data, open(_REG_FILE, "w"), ensure_ascii=False, indent=2)