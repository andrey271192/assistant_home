"""Home Assistant REST API client."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .. import config

logger = logging.getLogger("assistant_home.ha")

CONTROLLABLE_DOMAINS = frozenset(
    {"light", "switch", "cover", "climate", "fan", "input_boolean", "media_player", "scene"}
)


class HAError(Exception):
    pass


def _headers() -> dict[str, str]:
    tok = config.HA_TOKEN
    if not tok:
        raise HAError("HA_TOKEN not configured")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _base() -> str:
    url = config.HA_URL
    if not url:
        raise HAError("HA_URL not configured")
    return url


async def health() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{_base()}/api/", headers=_headers())
        if r.status_code >= 400:
            raise HAError(f"HA API {r.status_code}: {r.text[:200]}")
        return r.json()


async def get_state(entity_id: str) -> dict[str, Any]:
    eid = str(entity_id)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{_base()}/api/states/{eid}", headers=_headers())
        if r.status_code == 404:
            raise HAError(f"Entity not found: {eid}")
        if r.status_code >= 400:
            raise HAError(f"HA states {r.status_code}")
        return r.json()


async def get_states(entity_ids: list[str]) -> list[dict[str, Any]]:
    if not entity_ids:
        return []
    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        for eid in entity_ids:
            try:
                r = await client.get(
                    f"{_base()}/api/states/{eid}",
                    headers=_headers(),
                )
                if r.status_code == 200:
                    out.append(r.json())
            except Exception as e:
                logger.warning("state %s: %s", eid, e)
    return out


def _domain_service(entity_id: str, turn_on: bool) -> tuple[str, str, dict[str, Any]]:
    domain = entity_id.split(".")[0]
    data: dict[str, Any] = {"entity_id": entity_id}
    if domain == "light":
        return "light", "turn_on" if turn_on else "turn_off", data
    if domain == "switch":
        return "switch", "turn_on" if turn_on else "turn_off", data
    if domain == "cover":
        return "cover", "open" if turn_on else "close", data
    if domain == "climate":
        return "climate", "turn_on" if turn_on else "turn_off", data
    if domain == "fan":
        return "fan", "turn_on" if turn_on else "turn_off", data
    if domain == "input_boolean":
        return "input_boolean", "turn_on" if turn_on else "turn_off", data
    return domain, "turn_on" if turn_on else "turn_off", data


async def set_entity(entity_id: str, turn_on: bool) -> None:
    domain, service, data = _domain_service(entity_id, turn_on)
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{_base()}/api/services/{domain}/{service}",
            headers=_headers(),
            json=data,
        )
        if r.status_code >= 400:
            raise HAError(f"HA service {domain}.{service}: {r.status_code} {r.text[:200]}")


def is_controllable(entity_id: str) -> bool:
    domain = str(entity_id).split(".")[0]
    return domain in CONTROLLABLE_DOMAINS


async def toggle_entity(entity_id: str) -> dict[str, Any]:
    if not is_controllable(entity_id):
        raise HAError("Entity is read-only")
    st = await get_state(entity_id)
    state = (st.get("state") or "off").lower()
    domain = str(entity_id).split(".")[0]
    if domain == "fan":
        on = state in ("off", "unavailable", "unknown")
    else:
        on = state in ("off", "closed", "unavailable", "unknown")
    await set_entity(entity_id, on)
    return await get_state(entity_id)


async def set_automation_enabled(entity_id: str, enabled: bool) -> dict[str, Any]:
    eid = str(entity_id)
    if not eid.startswith("automation."):
        raise HAError("Not an automation entity")
    service = "turn_on" if enabled else "turn_off"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{_base()}/api/services/automation/{service}",
            headers=_headers(),
            json={"entity_id": eid},
        )
        if r.status_code >= 400:
            raise HAError(f"automation.{service}: {r.status_code} {r.text[:200]}")
    return await get_state(eid)


async def toggle_automation_enabled(entity_id: str) -> dict[str, Any]:
    st = await get_state(entity_id)
    enabled = (st.get("state") or "off").lower() == "on"
    return await set_automation_enabled(entity_id, not enabled)


async def trigger_automation(entity_id: str) -> None:
    eid = str(entity_id)
    if not eid.startswith("automation."):
        raise HAError("Not an automation entity")
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{_base()}/api/services/automation/trigger",
            headers=_headers(),
            json={"entity_id": eid},
        )
        if r.status_code >= 400:
            raise HAError(f"automation.trigger: {r.status_code} {r.text[:200]}")


def state_label(state: str, domain: str = "") -> str:
    s = (state or "unknown").lower()
    if domain == "binary_sensor":
        if s == "on":
            return "Сработал"
        if s == "off":
            return "Норма"
    if s in ("on", "open", "heat", "cool", "playing", "home"):
        return "Вкл"
    if s in ("off", "closed"):
        return "Выкл"
    if s == "unavailable":
        return "Нет связи"
    return state


def state_summary(st: dict[str, Any]) -> dict[str, Any]:
    attrs = st.get("attributes") or {}
    eid = st.get("entity_id") or ""
    domain = eid.split(".")[0] if "." in eid else ""
    state = st.get("state") or "unknown"
    friendly = attrs.get("friendly_name") or eid
    unit = attrs.get("unit_of_measurement") or ""
    sl = state.lower()
    if domain == "fan":
        is_on = sl not in ("off", "unavailable", "unknown")
    elif domain == "binary_sensor":
        is_on = sl == "on"
    elif domain == "automation":
        is_on = sl == "on"
    else:
        is_on = sl in ("on", "open", "heat", "cool", "playing", "home")
    return {
        "entity_id": eid,
        "state": state,
        "state_label": state_label(state, domain),
        "friendly_name": friendly,
        "domain": domain,
        "unit": unit,
        "is_on": is_on,
        "controllable": is_controllable(eid),
    }
