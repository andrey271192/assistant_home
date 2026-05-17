#!/usr/bin/env python3
"""Build server/data/rooms.json from Home Assistant (areas + states)."""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "server" / "data" / "rooms.json"

CONTROL_DOMAINS = frozenset(
    {"light", "switch", "cover", "climate", "fan", "input_boolean", "media_player", "scene"}
)
STATUS_DOMAINS = frozenset({"binary_sensor"})
AUTOMATION_DOMAIN = "automation"
SKIP_DOMAINS = frozenset(
    {
        "number",
        "select",
        "update",
        "button",
        "device_tracker",
        "sensor",
        "event",
        "text",
        "time",
        "date",
        "datetime",
        "image",
        "camera",
        "weather",
        "zone",
        "person",
        "sun",
        "moon",
    }
)

AREA_ICONS = {
    "gostinaia": "🛋",
    "zal": "🛋",
    "spalnia": "🛏",
    "kukhnia": "🍳",
    "vannaia": "🛁",
    "prikhozhaia": "🚪",
    "koridor": "🚪",
    "kabinet": "💼",
    "balkon": "🌿",
    "ulitsa": "🌳",
    "server": "🖥",
    "server_nas": "💾",
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", (s or "").lower()).strip("_")


def _ha_client() -> tuple[str, str]:
    url = (os.getenv("HA_URL") or "").rstrip("/")
    token = (os.getenv("HA_TOKEN") or "").strip()
    if not url or not token:
        env = ROOT / "server" / ".env"
        if env.is_file():
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == "HA_URL" and not url:
                    url = v.rstrip("/")
                if k == "HA_TOKEN" and not token:
                    token = v
    if not url or not token:
        sys.exit("Set HA_URL and HA_TOKEN in server/.env")
    return url, token


def _template(url: str, headers: dict, tpl: str) -> str:
    r = httpx.post(
        f"{url}/api/template",
        headers=headers,
        json={"template": tpl},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.text.strip().strip('"')


def main() -> None:
    url, token = _ha_client()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    area_names: dict[str, str] = {}
    raw_names = _template(
        url,
        headers,
        '{% for a in areas() %}{{ a }}|{{ area_name(a) }}\n{% endfor %}',
    )
    for line in raw_names.splitlines():
        if "|" not in line:
            continue
        aid, name = line.split("|", 1)
        area_names[aid.strip()] = name.strip()

    area_entities: dict[str, list[str]] = defaultdict(list)
    raw_map = _template(
        url,
        headers,
        '{% for area in areas() %}{% for e in area_entities(area) %}{{ area }}|{{ e }}\n{% endfor %}{% endfor %}',
    )
    for line in raw_map.splitlines():
        if "|" not in line:
            continue
        aid, eid = line.split("|", 1)
        area_entities[aid.strip()].append(eid.strip())

    r = httpx.get(f"{url}/api/states", headers=headers, timeout=60.0)
    r.raise_for_status()
    states = {s["entity_id"]: s for s in r.json()}

    rooms: dict = {}
    for area_id in sorted(area_entities.keys()):
        ents = []
        autos = []
        for eid in area_entities[area_id]:
            st = states.get(eid)
            if not st:
                continue
            domain = eid.split(".")[0]
            if domain in SKIP_DOMAINS:
                continue
            attrs = st.get("attributes") or {}
            title = (attrs.get("friendly_name") or eid).strip()
            hidden = attrs.get("hidden") or attrs.get("entity_registry_visible_default") is False
            if hidden:
                continue
            if domain == AUTOMATION_DOMAIN:
                autos.append({"id": eid, "title": title})
                continue
            if domain not in CONTROL_DOMAINS and domain not in STATUS_DOMAINS:
                continue
            if domain in STATUS_DOMAINS:
                device_class = attrs.get("device_class") or ""
                if device_class not in (
                    "door",
                    "window",
                    "opening",
                    "motion",
                    "occupancy",
                    "presence",
                    "moisture",
                    "smoke",
                    "gas",
                    "problem",
                    "safety",
                ):
                    continue
            ents.append({"id": eid, "title": title, "type": domain})

        if not ents and not autos:
            continue

        title = area_names.get(area_id) or area_id.replace("_", " ").title()
        rooms[area_id] = {
            "title": title,
            "icon": AREA_ICONS.get(area_id, "🏠"),
            "entities": sorted(ents, key=lambda x: (x["type"], x["title"])),
            "automations": sorted(autos, key=lambda x: x["title"]),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rooms, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n_ent = sum(len(v.get("entities") or []) for v in rooms.values())
    n_auto = sum(len(v.get("automations") or []) for v in rooms.values())
    print(f"Wrote {OUT}: {len(rooms)} rooms, {n_ent} entities, {n_auto} automations")


if __name__ == "__main__":
    main()
