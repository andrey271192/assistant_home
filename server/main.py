"""Assistant Home — Telegram Mini App for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from . import config
from .api.tg_api import router as tg_router
from .services.telegram_bot import telegram_bot_loop

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("assistant_home")


def _read_tpl(name: str) -> str:
    path = config.TEMPLATES_DIR / name
    return path.read_text(encoding="utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(telegram_bot_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# Behind nginx with path prefix /ah/ use ROOT_PATH=/ah (see deploy/nginx)
_root = (__import__("os").getenv("ROOT_PATH") or "").strip().rstrip("/")

app = FastAPI(
    title="Assistant Home",
    lifespan=lifespan,
    docs_url=None if config.DISABLE_OPENAPI else "/docs",
    redoc_url=None,
    root_path=_root,
)
app.include_router(tg_router)


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "assistant_home"}


@app.get("/tg/app", response_class=HTMLResponse)
@app.get("/tg", response_class=HTMLResponse)
async def tg_miniapp_page():
    return HTMLResponse(_read_tpl("tg_miniapp.html"))


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(
        "<!DOCTYPE html><html><body style='font-family:sans-serif;padding:2rem'>"
        "<h1>Assistant Home</h1>"
        "<p>Telegram Mini App: <a href='/tg/app'>/tg/app</a></p>"
        "</body></html>"
    )
