from __future__ import annotations

import os
import json
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .market import CHINA_TZ, MarketClient, MarketDataError, normalize_code
from .store import CloudMarketStore
from .strategy import SellWindowEngine


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
ACCESS_TOKEN = os.getenv("APP_ACCESS_TOKEN", "").strip()
ALLOWED_ORIGINS = {
    "https://localhost",
    "http://localhost",
    "capacitor://localhost",
    *(
        origin.strip().rstrip("/")
        for origin in os.getenv("APP_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ),
}

app = FastAPI(
    title="北交所新股首日卖出窗口助手",
    version=__version__,
    docs_url="/api/docs" if os.getenv("ENABLE_API_DOCS") == "1" else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-App-Token"],
)
market = MarketClient()
engine = SellWindowEngine()
store = CloudMarketStore()
relay_quotes: dict[str, tuple[datetime, dict]] = {}
relay_lock = threading.RLock()


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
    if request.url.path.startswith("/api/") or request.url.path == "/service-worker.js":
        response.headers["Cache-Control"] = "no-store"
    else:
        response.headers["Cache-Control"] = "public, max-age=300"
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
        "strategy": "V3.2-adaptive-momentum",
        "storage": store.backend,
        "persistent": store.persistent,
    }


def _profile_payload(profile, saved: dict | None = None) -> dict | None:
    if profile is None and not saved:
        return None
    saved = saved or {}
    issue_price = saved.get("issuePrice") if saved.get("issuePrice") is not None else getattr(profile, "issue_price", None)
    return {
        "code": saved.get("code") or getattr(profile, "code", ""),
        "name": getattr(profile, "name", ""),
        "issuePrice": issue_price,
        "issuePe": getattr(profile, "issue_pe", None),
        "industryPe": getattr(profile, "industry_pe", None),
        "peDiscount": getattr(profile, "pe_discount_pct", None),
        "industry": getattr(profile, "industry", None),
        "mainBusiness": getattr(profile, "main_business", None),
        "listingDate": getattr(profile, "listing_date", None),
        "subscriptionDate": getattr(profile, "subscription_date", None),
        "issueShares": getattr(profile, "issue_shares", None),
        "firstDayTradableShares": saved.get("firstDayTradableShares"),
        "denominatorSource": saved.get("denominatorSource") or "",
        "denominatorVerified": bool(saved.get("denominatorVerified")),
        "firstDayUnlock": None,
        "industryHeat": 1,
        "notes": "首日流通盘和竞价盘口只有在公告或TQ中转核验后才参与强卖出判断。",
    }


def _live_session(minute: int) -> bool:
    return 565 <= minute <= 690 or 780 <= minute <= 900


def _market_phase(now: datetime) -> str:
    minute = now.hour * 60 + now.minute
    if minute < 565:
        return "pre_open"
    if minute < 570:
        return "auction"
    if 570 <= minute <= 690 or 780 <= minute <= 900:
        return "trading"
    if 690 < minute < 780:
        return "lunch"
    return "closed"


def _relay_quote(code: str) -> dict | None:
    with relay_lock:
        item = relay_quotes.get(code)
    if not item or (datetime.now(CHINA_TZ) - item[0]).total_seconds() > 15:
        return None
    return dict(item[1])


def _full_quote_payload(code: str, *, force: bool = False) -> tuple[dict, list[str]]:
    del force
    normalized = normalize_code(code)
    try:
        profile = market.profile(normalized)
    except Exception:
        profile = None
    saved = store.get_profile(normalized)
    profile_payload = _profile_payload(profile, saved)
    today = datetime.now(CHINA_TZ).date().isoformat()
    listing_date = str((profile_payload or {}).get("listingDate") or "")
    if listing_date and listing_date > today:
        raise HTTPException(
            status_code=409,
            detail=f"{normalized} 将于 {listing_date} 上市，当前暂无实时成交行情",
        )

    relay = _relay_quote(normalized)
    warnings: list[str] = []
    now = datetime.now(CHINA_TZ)
    if relay:
        row = relay
        row["source"] = str(row.get("source") or "TdxQuantRelay")
        market_timestamp = str(row.get("marketTimestamp") or row.get("capturedAt") or now.isoformat())
    else:
        quote, warnings = market.quote(normalized)
        row = {
            "code": quote.code, "name": quote.name, "price": quote.price,
            "open": quote.open, "high": quote.high, "low": quote.low,
            "previousClose": quote.previous_close, "vwap": quote.vwap,
            "turnover": quote.turnover_pct, "volumeShares": quote.volume_shares,
            "amountYuan": quote.amount_yuan, "floatMarketValue": quote.float_market_value,
            "marketTimestamp": quote.market_time.isoformat() if quote.market_time else None,
            "source": quote.source,
        }
        market_timestamp = str(row.get("marketTimestamp") or "")

    captured_at = now
    recorded = store.record_snapshot(row, captured_at)
    metrics = store.metrics(normalized, captured_at.date().isoformat())
    checkpoints = metrics["checkpoints"]
    custom_turnover = recorded.get("customTurnoverPct")
    minute = captured_at.hour * 60 + captured_at.minute
    opening30 = (checkpoints.get("m30_1000") or {}).get("turnoverPct")
    opening30_final = opening30 is not None
    if opening30 is None and 570 <= minute < 600:
        opening30 = custom_turnover
    auction = (checkpoints.get("auction_0925") or {}).get("turnoverPct")

    source_time = None
    try:
        source_time = datetime.fromisoformat(market_timestamp.replace("Z", "+00:00")).astimezone(CHINA_TZ)
    except (ValueError, AttributeError):
        pass
    age = max(0.0, (now - source_time).total_seconds()) if source_time else None
    stale = _live_session(minute) and (age is None or age > 20)
    denominator_verified = bool(recorded.get("denominatorVerified"))
    tq_primary = str(recorded.get("source") or "").startswith("TdxQuant")
    confidence = "high" if tq_primary and denominator_verified and not stale else ("medium" if denominator_verified and not stale else "low")
    recorded.update({
        "turnover": custom_turnover if custom_turnover is not None else recorded.get("turnover"),
        "openingTurnover30": opening30,
        "openingTurnover30Final": opening30_final,
        "rollingTurnover30": metrics.get("turnoverDelta30Pct"),
        "turnoverDelta5Pct": metrics.get("turnoverDelta5Pct"),
        "turnoverHistoryMinutes": metrics.get("turnoverHistoryMinutes"),
        "checkpoints": checkpoints,
        "auctionRatio": auction,
        "auctionCaptured": "auction_0925" in checkpoints,
        "auctionOrderBookImbalancePct": recorded.get("auctionOrderBookImbalancePct"),
        "auctionOrderBookReliable": bool(recorded.get("auctionOrderBookReliable") and tq_primary),
        "auctionOrderBookCapturedAt": recorded.get("auctionOrderBookCapturedAt"),
        "dataQuality": {
            "confidence": confidence, "primarySource": recorded.get("source"),
            "tqPrimary": tq_primary, "volumeNormalizedToShares": recorded.get("volumeShares") is not None,
            "denominatorReady": bool(recorded.get("firstDayTradableShares")),
            "denominatorVerified": denominator_verified, "denominatorSource": recorded.get("denominatorSource") or "",
            "persistent": store.persistent, "historicalTickAvailable": False,
            "auctionCaptured": "auction_0925" in checkpoints,
        },
        "marketPhase": _market_phase(now), "quoteFrozen": stale,
        "quoteFreshnessReason": "行情时间戳超过20秒" if stale else "",
        "unchangedSeconds": age if stale else 0,
        "crossChecked": False,
    })
    return recorded, warnings


@app.get("/api/profile", dependencies=[Depends(protect)])
def legacy_profile(code: str = Query(min_length=6, max_length=16), force: int = Query(default=0)) -> dict:
    del force
    normalized = normalize_code(code)
    try:
        profile = market.profile(normalized)
    except Exception as exc:
        profile = None
        if not store.get_profile(normalized):
            raise HTTPException(status_code=502, detail=f"发行资料读取失败：{exc}") from exc
    payload = _profile_payload(profile, store.get_profile(normalized))
    if not payload:
        raise HTTPException(status_code=404, detail=f"未找到发行资料 {normalized}")
    return {"ok": True, "source": "发行资料+云端核验流通盘", "profile": payload}


@app.post("/api/profile/save", dependencies=[Depends(protect)])
def save_profile(payload: dict = Body(...)) -> dict:
    saved = store.save_profile(payload)
    try:
        profile = market.profile(saved["code"])
    except Exception:
        profile = None
    return {"ok": True, "profile": _profile_payload(profile, saved)}


@app.get("/api/quote", dependencies=[Depends(protect)])
def legacy_quote(code: str = Query(min_length=6, max_length=16), force: int = Query(default=0)) -> dict:
    try:
        row, warnings = _full_quote_payload(code, force=bool(force))
    except HTTPException as exc:
        if exc.status_code == 409:
            normalized = normalize_code(code)
            try:
                profile = market.profile(normalized)
            except Exception:
                profile = None
            return JSONResponse(status_code=409, content={
                "ok": False, "preListing": True,
                "listingDate": getattr(profile, "listing_date", None), "error": exc.detail,
            })
        raise
    now = datetime.now(CHINA_TZ)
    timestamp = row.get("marketTimestamp")
    try:
        source_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).astimezone(CHINA_TZ)
        age = max(0.0, (now - source_at).total_seconds())
    except (ValueError, AttributeError):
        age = None
    stale = bool(row.get("quoteFrozen"))
    return {
        "ok": True, "source": row.get("source"), "updatedAt": now.isoformat(timespec="seconds"),
        "ageSeconds": age, "stale": stale, "consecutiveFailures": 0,
        "usingCache": False, "warnings": warnings, "quote": row,
    }


@app.get("/api/metrics", dependencies=[Depends(protect)])
def legacy_metrics(code: str = Query(min_length=6, max_length=16), date_value: str | None = Query(default=None, alias="date")) -> dict:
    return {"ok": True, "metrics": store.metrics(code, date_value)}


@app.post("/api/signal-event", dependencies=[Depends(protect)])
def save_signal_event(payload: dict = Body(...)) -> dict:
    return {"ok": True, "event": store.record_signal_event(payload)}


@app.get("/api/signal-events", dependencies=[Depends(protect)])
def get_signal_events(
    code: str = Query(min_length=6, max_length=16),
    date_value: str | None = Query(default=None, alias="date"),
    changes_only: int = Query(default=0, alias="changesOnly"),
    limit: int = Query(default=5000, ge=1, le=20000),
) -> dict:
    return {"ok": True, "archive": store.signal_events(code, date_value, changes_only=bool(changes_only), limit=limit)}


@app.get("/api/strategy-config", dependencies=[Depends(protect)])
def strategy_config() -> dict:
    path = ROOT / "strategy-v32.json"
    return {"ok": True, "source": "V3.2全样本参数", "parameters": json.loads(path.read_text(encoding="utf-8"))}


@app.post("/api/relay/quote", dependencies=[Depends(protect)])
def relay_quote(payload: dict = Body(...)) -> dict:
    code = normalize_code(str(payload.get("code") or ""))
    timestamp = str(payload.get("marketTimestamp") or payload.get("capturedAt") or "")
    try:
        captured = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(CHINA_TZ)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="TQ中转行情必须包含有效 marketTimestamp") from exc
    if abs((datetime.now(CHINA_TZ) - captured).total_seconds()) > 60:
        raise HTTPException(status_code=400, detail="拒绝超过60秒的TQ中转行情")
    cleaned = dict(payload)
    cleaned.update({"code": code, "source": "TdxQuantRelay", "marketTimestamp": captured.isoformat()})
    with relay_lock:
        relay_quotes[code] = (datetime.now(CHINA_TZ), cleaned)
    return {"ok": True, "acceptedAt": datetime.now(CHINA_TZ).isoformat(timespec="seconds")}


@app.get("/api/tdx/status", dependencies=[Depends(protect)])
def relay_status(probe: int = Query(default=0)) -> dict:
    del probe
    now = datetime.now(CHINA_TZ)
    with relay_lock:
        recent = [(code, item) for code, item in relay_quotes.items() if (now - item[0]).total_seconds() <= 15]
    ready = bool(recent)
    return {"ok": True, "status": {
        "processRunning": ready, "tqReady": ready, "tqChecking": False,
        "autostartEnabled": False, "autostartWindow": "云端不启动本机软件",
        "checkedAt": now.isoformat(timespec="seconds"), "executableAvailable": False,
        "tqError": "等待本机TQ中转" if not ready else "", "startupGrace": False,
    }}


@app.post("/api/tdx/start", dependencies=[Depends(protect)])
def relay_start() -> JSONResponse:
    return JSONResponse(status_code=409, content={"ok": False, "error": "云端不能启动你电脑上的通达信；请启动可选的本机TQ中转。"})


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
    today = datetime.now(CHINA_TZ).date().isoformat()
    if profile and profile.listing_date and profile.listing_date > today:
        raise HTTPException(
            status_code=409,
            detail=f"{profile.name or normalized}（{normalized}）尚未上市，上市日期为 {profile.listing_date}。请在上市首日开盘后再判断卖出窗口。",
        )
    try:
        quote, fallback_warnings = market.quote(normalized)
    except MarketDataError as exc:
        if profile and not profile.listing_date:
            raise HTTPException(
                status_code=409,
                detail=f"{profile.name or normalized}（{normalized}）尚未上市或上市日期尚未公布，当前没有可用于卖出判断的交易行情。请等待上市公告，并在上市首日开盘后再使用。",
            ) from exc
        raise
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


@app.get("/service-worker.js", include_in_schema=False)
def service_worker():
    response = FileResponse(STATIC / "service-worker.js", media_type="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


app.mount("/static", StaticFiles(directory=STATIC), name="static")
