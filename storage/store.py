#!/usr/bin/env python3
"""持久化存储 - 支持每个子bot独立数据"""
import json, os, threading

_LOCK = threading.Lock()


def _data_dir(bot_id: str) -> str:
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bot_data", str(bot_id))
    os.makedirs(base, exist_ok=True)
    return base


def _path(bot_id: str, name: str) -> str:
    return os.path.join(_data_dir(bot_id), name + ".json")


def _load(bot_id: str, name: str) -> dict:
    p = _path(bot_id, name)
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            return {}
    return {}


def _save(bot_id: str, name: str, data: dict):
    with _LOCK:
        json.dump(data, open(_path(bot_id, name), "w"), ensure_ascii=False)


# 验证
def is_verified(bot_id: str, uid: int) -> bool:
    return uid in _load(bot_id, "verified")


def set_verified(bot_id: str, uid: int, v: bool):
    d = _load(bot_id, "verified")
    d[str(uid)] = v
    _save(bot_id, "verified", d)


# 屏蔽
def is_blocked(bot_id: str, uid: int) -> bool:
    return _load(bot_id, "blocked").get(str(uid), False)


def set_blocked(bot_id: str, uid: int, b: bool):
    d = _load(bot_id, "blocked")
    d[str(uid)] = b
    _save(bot_id, "blocked", d)