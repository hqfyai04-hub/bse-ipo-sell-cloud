from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .market import CHINA_TZ, MarketClient, MarketDataError, normalize_code
from .strategy import SellWindowEngine


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
ACCESS_TOKEN = os.getenv("APP_ACCESS_TOKEN", "").strip()

app = FastAPI(
    title="北交所新股首日卖出窗口助手",
    version=__version__,
    docs_url="/api/docs" if os.getenv("ENABLE_API_DOCS") == "1" else None,
    redoc_url=None,
)
market = MarketClient()
engine = SellWindowEngine()


class RateLimiter:
    def __init__(self, limit: int = 120, window: int = 60) -> None:
        self.limit = limit
        self.window = window
        self.events: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, client: str) -> None:
        now = time.monotonic()
        with self.lock:
            bucket = self.events[client]
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")
            bucket.append(now)


limiter = RateLimiter()


def protect(
    request: Request,
    token: str | None = Query(default=None),
    x_app_token: str | None = Header(default=None),
) -> None:
    client = request.client.host if request.client else "unknown"
    limiter.check(client)
    if ACCESS_TOKEN and (x_app_token or token or "") != ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="需要有效访问口令")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "public, max-age=300"
    return response


@app.exception_handler(MarketDataError)
async def market_error(_: Request, exc: MarketDataError):
    return JSONResponse(status_code=502, content={"ok": False, "error": str(exc)})


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "bse-ipo-sell-cloud",
        "version": __version__,
        "server_time": datetime.now(CHINA_TZ).isoformat(timespec="seconds"),
        "protected": bool(ACCESS_TOKEN),
    }


@app.get("/api/analyze", dependencies=[Depends(protect)])
def analyze(
    code: str = Query(min_length=6, max_length=16),
    position: int | None = Query(default=None, ge=1, le=10_000_000),
) -> dict:
    try:
        normalized = normalize_code(code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profile_error = ""
    try:
        profile = market.profile(normalized)
    except Exception as exc:
        profile = None
        profile_error = str(exc)
    quote, fallback_warnings = market.quote(normalized)
    decision = engine.analyze(quote, profile, position=position)
    warnings = list(decision.warnings)
    if fallback_warnings:
        warnings.append("主行情源降级：" + "；".join(fallback_warnings))
    if profile_error:
        warnings.append("发行资料接口异常：" + profile_error)
    decision.warnings = warnings
    return {
        "ok": True,
        "version": __version__,
        "server_time": datetime.now(CHINA_TZ).isoformat(timespec="seconds"),
        "quote": quote.public(),
        "profile": profile.public() if profile else None,
        "decision": decision.public(),
        "disclaimer": "本软件只识别卖出窗口，不预测最高价、不连接券商、不自动下单。执行前请以券商终端为准。",
    }


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
