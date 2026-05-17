"""Telegram bot — /start, /pin, Mini App launcher."""
from __future__ import annotations

import asyncio
import logging

import httpx

from .. import config
from . import telegram_auth as tgauth
from .access_control import telegram_user_allowed

logger = logging.getLogger("assistant_home.tg")
_offset = 0


def _api(method: str, **kwargs) -> str:
    return f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{method}"


def _webapp_url() -> str:
    return f"{config.PUBLIC_BASE_URL.rstrip('/')}/tg/app"


async def _send(chat_id: int | str, text: str, reply_markup: dict | None = None) -> None:
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(_api("sendMessage"), json=payload)


def _main_kb() -> dict:
    rows: list[list[dict]] = []
    url = _webapp_url()
    if url.lower().startswith("https://"):
        rows.append([{"text": "🏠 Дом", "web_app": {"url": url}}])
    rows.append([{"text": "🔐 PIN", "callback_data": "pin_hint"}])
    return {"inline_keyboard": rows}


async def _handle_message(msg: dict) -> None:
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    user = msg.get("from") or {}
    user_id = str(user.get("id") or "")
    if not chat_id or not telegram_user_allowed(user_id):
        await _send(chat_id, "⛔ Нет доступа к этому боту.")
        return

    text = (msg.get("text") or "").strip()
    low = text.lower()

    if low.startswith("/start") or low == "help":
        pin_line = (
            "🔐 Управление: /pin КОД (сессия на несколько часов)."
            if tgauth.pin_configured()
            else "🔐 PIN не настроен — управление без PIN."
        )
        await _send(
            chat_id,
            "🏠 <b>Assistant Home</b>\n\n"
            "Умный дом через Home Assistant.\n"
            f"{pin_line}\n\n"
            "Откройте Mini App кнопкой ниже.",
            reply_markup=_main_kb(),
        )
        return

    if low.startswith("/pin"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await _send(
                chat_id,
                "Формат: <code>/pin 1234</code>\n"
                "Сброс: <code>/pin off</code>",
            )
            return
        arg = parts[1].strip()
        if arg.lower() == "off":
            tgauth.clear_pin_session(user_id)
            await _send(chat_id, "🔓 PIN-сессия сброшена.")
            return
        if not tgauth.pin_configured():
            await _send(chat_id, "PIN не настроен в .env (TELEGRAM_PIN).")
            return
        if tgauth.check_pin(arg):
            tgauth.grant_pin_session(user_id)
            boot = tgauth.issue_bootstrap(user_id)
            url = f"{_webapp_url()}?b={boot}"
            await _send(
                chat_id,
                f"✅ PIN принят (~{config.TELEGRAM_PIN_SESSION_HOURS:.0f} ч).\n"
                f'<a href="{url}">Открыть Mini App</a>',
                reply_markup=_main_kb(),
            )
        else:
            await _send(chat_id, "❌ Неверный PIN.")
        return

    await _send(chat_id, "Команды: /start · /pin · кнопка 🏠 Дом", reply_markup=_main_kb())


async def _handle_callback(cb: dict) -> None:
    data = (cb.get("data") or "").strip()
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    user = cb.get("from") or {}
    user_id = str(user.get("id") or "")
    if not chat_id:
        return
    if data == "pin_hint":
        await _send(
            chat_id,
            "Введите <code>/pin КОД</code> в чат, затем откройте Mini App.",
        )


async def telegram_bot_loop() -> None:
    if not config.TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN empty — bot disabled")
        while True:
            await asyncio.sleep(3600)
        return

    global _offset
    logger.info("Telegram bot started")
    while True:
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                r = await client.get(
                    _api("getUpdates"),
                    params={"offset": _offset, "timeout": 25},
                )
                data = r.json()
            if not data.get("ok"):
                await asyncio.sleep(5)
                continue
            for upd in data.get("result") or []:
                _offset = max(_offset, int(upd.get("update_id", 0)) + 1)
                if "message" in upd:
                    await _handle_message(upd["message"])
                elif "callback_query" in upd:
                    await _handle_callback(upd["callback_query"])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("telegram poll: %s", e)
            await asyncio.sleep(5)
