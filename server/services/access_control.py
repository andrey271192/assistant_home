"""Room / entity ACL per Telegram user id."""
from __future__ import annotations

from typing import Any

from .. import config
from ..database import load_json


def _access() -> dict[str, Any]:
    return load_json(config.ACCESS_FILE, {"users": {}, "allowed_ids": []})


def _rooms() -> dict[str, Any]:
    return load_json(config.ROOMS_FILE, {})


def telegram_user_allowed(user_id: str) -> bool:
    uid = str(user_id)
    env_ids = set(config.TELEGRAM_ALLOWED_IDS)
    if env_ids and uid in env_ids:
        return True
    data = _access()
    allowed = {str(x) for x in (data.get("allowed_ids") or [])}
    users = data.get("users") or {}
    if uid in allowed or uid in users:
        return True
    return not env_ids and not allowed and not users


def user_record(user_id: str) -> dict[str, Any]:
    users = (_access().get("users") or {})
    return dict(users.get(str(user_id)) or {})


def is_admin(user_id: str) -> bool:
    rec = user_record(user_id)
    return rec.get("role") == "admin"


def allowed_room_ids(user_id: str) -> list[str] | None:
    if is_admin(user_id):
        return None
    rec = user_record(user_id)
    rooms = rec.get("rooms") or []
    if "*" in rooms:
        return None
    return [str(r) for r in rooms]


def _parse_entity_list(items: list) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ent in items or []:
        if isinstance(ent, str):
            out.append({"id": ent, "title": ent, "type": _guess_type(ent)})
        elif isinstance(ent, dict) and ent.get("id"):
            out.append(
                {
                    "id": str(ent["id"]),
                    "title": ent.get("title") or ent["id"],
                    "type": ent.get("type") or _guess_type(str(ent["id"])),
                }
            )
    return out


def list_rooms_for_user(user_id: str) -> list[dict[str, Any]]:
    all_rooms = _rooms()
    allowed = allowed_room_ids(user_id)
    out: list[dict[str, Any]] = []
    for rid, meta in all_rooms.items():
        if allowed is not None and rid not in allowed:
            continue
        if not isinstance(meta, dict):
            continue
        dev = len(meta.get("entities") or [])
        st = len(meta.get("status") or [])
        auto = len(meta.get("automations") or [])
        out.append(
            {
                "id": rid,
                "title": meta.get("title") or rid,
                "icon": meta.get("icon") or "🏠",
                "device_count": dev,
                "status_count": st,
                "automation_count": auto,
            }
        )
    out.sort(key=lambda x: (x.get("title") or "").lower())
    return out


def room_detail(user_id: str, room_id: str) -> dict[str, Any] | None:
    allowed = allowed_room_ids(user_id)
    if allowed is not None and room_id not in allowed:
        return None
    meta = _rooms().get(room_id)
    if not isinstance(meta, dict):
        return None
    return {
        "id": room_id,
        "title": meta.get("title") or room_id,
        "icon": meta.get("icon") or "🏠",
        "entities": _parse_entity_list(meta.get("entities") or []),
        "status": _parse_entity_list(meta.get("status") or []),
        "automations": _parse_entity_list(meta.get("automations") or []),
    }


def _entity_in_room_lists(detail: dict[str, Any], entity_id: str) -> bool:
    eid = str(entity_id)
    for key in ("entities", "status"):
        for ent in detail.get(key) or []:
            if ent.get("id") == eid:
                return True
    return False


def entity_allowed(user_id: str, entity_id: str) -> bool:
    eid = str(entity_id)
    for rid in _rooms():
        detail = room_detail(user_id, rid)
        if detail and _entity_in_room_lists(detail, eid):
            return True
    return False


def automation_allowed(user_id: str, entity_id: str) -> bool:
    eid = str(entity_id)
    for rid in _rooms():
        detail = room_detail(user_id, rid)
        if not detail:
            continue
        for auto in detail.get("automations") or []:
            if auto.get("id") == eid:
                return True
    return False


def _guess_type(entity_id: str) -> str:
    return entity_id.split(".")[0] if "." in entity_id else "switch"
