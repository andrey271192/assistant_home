"""Telegram Mini App API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .. import config
from ..services import access_control as acl
from ..services import homeassistant as ha
from ..services import telegram_auth as tgauth

router = APIRouter(prefix="/api/tg", tags=["telegram"])


def _init_from_headers(request: Request) -> str:
    return (
        request.headers.get("X-Telegram-Init-Data")
        or request.headers.get("x-telegram-init-data")
        or ""
    ).strip()


def _resolve_user(
    request: Request,
    body: dict | None = None,
    *,
    allow_bootstrap: bool = False,
) -> tuple[str, dict[str, Any]]:
    body = body or {}
    boot = (body.get("bootstrap") or request.query_params.get("b") or "").strip()
    if allow_bootstrap and boot:
        user_id = tgauth.consume_bootstrap(boot)
        if not user_id or not acl.telegram_user_allowed(user_id):
            raise HTTPException(401, "Ссылка устарела — снова /pin в боте")
        return user_id, {}

    init_data = _init_from_headers(request) or (body.get("init_data") or "").strip()
    if not init_data:
        raise HTTPException(401, "Откройте Mini App из бота")
    parsed = tgauth.validate_webapp_init_data(init_data, config.TELEGRAM_TOKEN)
    if not parsed:
        raise HTTPException(401, "Неверный initData — проверьте TELEGRAM_TOKEN")
    user_id = tgauth.user_id_from_init_data(parsed)
    if not user_id or not acl.telegram_user_allowed(user_id):
        raise HTTPException(403, "Нет доступа")
    return user_id, parsed


def _require_pin(user_id: str) -> None:
    if tgauth.pin_configured() and not tgauth.pin_session_ok(user_id):
        raise HTTPException(403, "Нужен PIN")


@router.post("/auth")
async def tg_auth(request: Request, body: dict | None = None):
    body = body or {}
    user_id, parsed = _resolve_user(request, body, allow_bootstrap=True)
    pin = (body.get("pin") or "").strip()
    if pin:
        if not tgauth.check_pin(pin):
            raise HTTPException(403, "Неверный PIN")
        tgauth.grant_pin_session(user_id)
    pin_ok = tgauth.pin_session_ok(user_id)
    token = tgauth.issue_web_session(user_id) if pin_ok else ""
    user = parsed.get("user") if isinstance(parsed.get("user"), dict) else {}
    return {
        "ok": True,
        "user_id": user_id,
        "pin_ok": pin_ok,
        "pin_required": tgauth.pin_configured(),
        "session_token": token,
        "user": {
            "id": user.get("id"),
            "first_name": user.get("first_name"),
            "username": user.get("username"),
        },
        "webapp_url": f"{config.PUBLIC_BASE_URL}/tg/app",
    }


@router.get("/me")
async def tg_me(request: Request, x_tg_session: str = Header("")):
    user_id, _ = _resolve_user(request)
    if x_tg_session and tgauth.user_id_from_web_token(x_tg_session) != user_id:
        raise HTTPException(401, "Сессия не совпадает")
    rec = acl.user_record(user_id)
    return {
        "ok": True,
        "user_id": user_id,
        "name": rec.get("name") or "",
        "role": rec.get("role") or "user",
        "pin_ok": tgauth.pin_session_ok(user_id),
        "pin_required": tgauth.pin_configured(),
    }


@router.get("/health")
async def tg_ha_health(request: Request):
    _resolve_user(request)
    try:
        info = await ha.health()
        return {"ok": True, "ha": info}
    except ha.HAError as e:
        return {"ok": False, "error": str(e)}


@router.get("/rooms")
async def tg_rooms(request: Request):
    user_id, _ = _resolve_user(request)
    rooms = acl.list_rooms_for_user(user_id)
    return {"ok": True, "rooms": rooms}


def _merge_states(items: list[dict], states_map: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    for ent in items:
        eid = ent["id"]
        summ = states_map.get(eid) or {
            "entity_id": eid,
            "state": "unavailable",
            "state_label": "Нет связи",
            "friendly_name": ent.get("title") or eid,
            "domain": ent.get("type") or "switch",
            "unit": "",
            "is_on": False,
            "controllable": ha.is_controllable(eid),
        }
        out.append({**ent, **summ})
    return out


@router.get("/room/{room_id}")
async def tg_room(room_id: str, request: Request):
    user_id, _ = _resolve_user(request)
    detail = acl.room_detail(user_id, room_id)
    if not detail:
        raise HTTPException(404, "Комната не найдена или нет доступа")
    all_ids = (
        [e["id"] for e in detail.get("entities") or []]
        + [e["id"] for e in detail.get("status") or []]
        + [a["id"] for a in detail.get("automations") or []]
    )
    states = await ha.get_states(all_ids)
    by_id = {s.get("entity_id"): ha.state_summary(s) for s in states}
    return {
        "ok": True,
        "room": {
            "id": detail["id"],
            "title": detail["title"],
            "icon": detail["icon"],
            "entities": _merge_states(detail.get("entities") or [], by_id),
            "status": _merge_states(detail.get("status") or [], by_id),
            "automations": _merge_states(detail.get("automations") or [], by_id),
        },
    }


@router.post("/entity/toggle")
async def tg_toggle(request: Request, body: dict):
    user_id, _ = _resolve_user(request, body)
    _require_pin(user_id)
    eid = (body.get("entity_id") or "").strip()
    if not eid or not acl.entity_allowed(user_id, eid):
        raise HTTPException(403, "Сущность недоступна")
    try:
        st = await ha.toggle_entity(eid)
        return {"ok": True, "entity": ha.state_summary(st)}
    except ha.HAError as e:
        raise HTTPException(502, str(e)) from e


@router.post("/automation/trigger")
async def tg_automation_trigger(request: Request, body: dict):
    user_id, _ = _resolve_user(request, body)
    _require_pin(user_id)
    eid = (body.get("entity_id") or "").strip()
    if not eid or not acl.automation_allowed(user_id, eid):
        raise HTTPException(403, "Автоматизация недоступна")
    try:
        await ha.trigger_automation(eid)
        return {"ok": True, "entity_id": eid, "action": "trigger"}
    except ha.HAError as e:
        raise HTTPException(502, str(e)) from e


@router.post("/automation/toggle")
async def tg_automation_toggle(request: Request, body: dict):
    """Включить/выключить автоматизацию (automation.turn_on/off)."""
    user_id, _ = _resolve_user(request, body)
    _require_pin(user_id)
    eid = (body.get("entity_id") or "").strip()
    if not eid or not acl.automation_allowed(user_id, eid):
        raise HTTPException(403, "Автоматизация недоступна")
    try:
        st = await ha.toggle_automation_enabled(eid)
        return {"ok": True, "entity": ha.state_summary(st)}
    except ha.HAError as e:
        raise HTTPException(502, str(e)) from e
