"""Telegram Mini App: initData validation, PIN sessions, bootstrap links."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl

from .. import config
from ..database import load_json, save_json

logger = logging.getLogger("assistant_home.tg.auth")


def _sessions() -> dict[str, Any]:
    return load_json(config.SESSIONS_FILE, {"chat": {}, "token": {}, "bootstrap": {}})


def _save_sessions(st: dict[str, Any]) -> None:
    save_json(config.SESSIONS_FILE, st)


def pin_configured() -> bool:
    return bool(config.TELEGRAM_PIN)


def check_pin(pin: str) -> bool:
    expected = config.TELEGRAM_PIN
    got = (pin or "").strip()
    if not expected or not got:
        return False
    return hmac.compare_digest(got.encode("utf-8"), expected.encode("utf-8"))


def pin_session_ok(user_id: int | str) -> bool:
    if not pin_configured():
        return True
    sid = str(user_id)
    rec = (_sessions().get("chat") or {}).get(sid) or {}
    return float(rec.get("pin_exp") or 0) > time.time()


def grant_pin_session(user_id: int | str) -> None:
    sid = str(user_id)
    st = _sessions()
    chats = st.setdefault("chat", {})
    chats[sid] = {
        "pin_exp": time.time() + config.TELEGRAM_PIN_SESSION_HOURS * 3600,
        "granted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _save_sessions(st)


def clear_pin_session(user_id: int | str) -> None:
    sid = str(user_id)
    st = _sessions()
    chats = st.get("chat") or {}
    chats.pop(sid, None)
    st["chat"] = chats
    _save_sessions(st)


def issue_web_session(user_id: int | str) -> str:
    if not pin_session_ok(user_id):
        return ""
    tok = secrets.token_urlsafe(24)
    st = _sessions()
    tokens = st.setdefault("token", {})
    now = time.time()
    for k, v in list(tokens.items()):
        if float((v or {}).get("exp") or 0) < now:
            tokens.pop(k, None)
    tokens[tok] = {
        "user_id": str(user_id),
        "exp": now + config.TELEGRAM_PIN_SESSION_HOURS * 3600,
    }
    _save_sessions(st)
    return tok


def user_id_from_web_token(token: str) -> str | None:
    tok = (token or "").strip()
    if not tok:
        return None
    rec = (_sessions().get("token") or {}).get(tok)
    if not rec or float(rec.get("exp") or 0) < time.time():
        return None
    return str(rec.get("user_id") or "")


def validate_webapp_init_data(init_data: str, bot_token: str) -> dict[str, Any] | None:
    raw = (init_data or "").strip()
    tok = (bot_token or "").strip()
    if not raw or not tok:
        return None
    try:
        pairs = parse_qsl(raw, keep_blank_values=True)
        data = dict(pairs)
        recv_hash = data.pop("hash", None)
        if not recv_hash:
            return None
        check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
        secret = hmac.new(b"WebAppData", tok.encode("utf-8"), hashlib.sha256).digest()
        calc = hmac.new(secret, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, str(recv_hash)):
            return None
        auth_date = int(data.get("auth_date") or 0)
        if auth_date and time.time() - auth_date > 86400 * 7:
            return None
        if data.get("user"):
            data["user"] = json.loads(data["user"])
        return data
    except Exception as e:
        logger.debug("initData failed: %s", e)
        return None


def user_id_from_init_data(parsed: dict[str, Any]) -> str:
    user = parsed.get("user")
    if isinstance(user, dict) and user.get("id") is not None:
        return str(user["id"])
    return ""


def issue_bootstrap(user_id: int | str, ttl_sec: int = 900) -> str:
    tok = secrets.token_urlsafe(18)
    st = _sessions()
    boots = st.setdefault("bootstrap", {})
    now = time.time()
    for k, v in list(boots.items()):
        if float((v or {}).get("exp") or 0) < now:
            boots.pop(k, None)
    boots[tok] = {"user_id": str(user_id), "exp": now + ttl_sec}
    _save_sessions(st)
    return tok


def consume_bootstrap(token: str) -> str | None:
    tok = (token or "").strip()
    if not tok:
        return None
    st = _sessions()
    boots = st.get("bootstrap") or {}
    rec = boots.get(tok)
    if not rec or float(rec.get("exp") or 0) < time.time():
        return None
    boots.pop(tok, None)
    st["bootstrap"] = boots
    _save_sessions(st)
    return str(rec.get("user_id") or "") or None
