from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# China Standard Time has been UTC+8 without daylight-saving changes since 1991.
# A fixed offset also keeps minimal Windows/Python images independent of tzdata.
CHINA_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
USER_AGENT = "Mozilla/5.0 (compatible; BSE-IPO-Sell-Cloud/1.0)"


class MarketDataError(RuntimeError):
    pass


def _number(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def normalize_code(value: str) -> str:
    code = re.sub(r"\D", "", str(value or ""))
    if len(code) != 6:
        raise ValueError("请输入 6 位证券代码")
    if code[0] not in {"4", "8", "9"}:
        raise ValueError("该代码不像北交所证券代码，请核对后重试")
    return code


def _get_bytes(url: str, *, referer: str, timeout: float = 8) -> bytes:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Referer": referer, "Accept": "*/*"},
    )
    with urlopen(request, timeout=timeout) as response:
        if response.status >= 400:
            raise MarketDataError(f"行情服务返回 HTTP {response.status}")
        return response.read()


def _get_json(url: str, params: dict[str, Any], *, referer: str, timeout: float = 10) -> dict[str, Any]:
    separator = "&" if "?" in url else "?"
    raw = _get_bytes(f"{url}{separator}{urlencode(params)}", referer=referer, timeout=timeout)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarketDataError("行情服务返回了无法解析的数据") from exc


def _parse_market_time(value: Any) -> datetime | None:
    text = re.sub(r"\D", "", str(value or ""))
    for fmt, size in (("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12)):
        if len(text) >= size:
            try:
                return datetime.strptime(text[:size], fmt).replace(tzinfo=CHINA_TZ)
            except ValueError:
                pass
    return None


@dataclass(slots=True)
class Quote:
    code: str
    name: str
    price: float | None
    open: float | None
    high: float | None
    low: float | None
    previous_close: float | None
    vwap: float | None
    turnover_pct: float | None
    volume_shares: float | None
    amount_yuan: float | None
    float_market_value: float | None
    market_time: datetime | None
    received_at: datetime
    source: str

    def public(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["market_time"] = self.market_time.isoformat() if self.market_time else None
        payload["received_at"] = self.received_at.isoformat()
        return payload


@dataclass(slots=True)
class IpoProfile:
    code: str
    name: str
    issue_price: float | None
    issue_pe: float | None
    industry_pe: float | None
    pe_discount_pct: float | None
    industry: str | None
    main_business: str | None
    listing_date: str | None
    subscription_date: str | None
    issue_shares: float | None
    source: str = "东方财富发行资料"

    def public(self) -> dict[str, Any]:
        return asdict(self)


def fetch_tencent_quote(code: str) -> Quote:
    code = normalize_code(code)
    raw = _get_bytes(
        f"https://qt.gtimg.cn/q=bj{code}",
        referer="https://stockapp.finance.qq.com/",
    ).decode("gbk", errors="ignore")
    if '="' not in raw:
        raise MarketDataError("腾讯行情未返回该代码")
    parts = raw.split('="', 1)[1].rsplit('"', 1)[0].split("~")
    if len(parts) < 48 or not parts[2]:
        raise MarketDataError("腾讯行情格式异常或代码不存在")
    returned = re.sub(r"\D", "", parts[2]).zfill(6)
    if returned != code:
        raise MarketDataError("行情代码交叉校验失败")

    volume_lots = _number(parts[36])
    amount_wan = _number(parts[37])
    volume_shares = volume_lots * 100 if volume_lots is not None else None
    amount_yuan = amount_wan * 10_000 if amount_wan is not None else None
    vwap = _number(parts[51]) if len(parts) > 51 else None
    if not vwap and amount_yuan and volume_shares:
        vwap = amount_yuan / volume_shares
    float_cap_yi = _number(parts[44])
    return Quote(
        code=code,
        name=parts[1].strip(),
        price=_number(parts[3]),
        previous_close=_number(parts[4]),
        open=_number(parts[5]),
        high=_number(parts[33]),
        low=_number(parts[34]),
        volume_shares=volume_shares,
        amount_yuan=amount_yuan,
        turnover_pct=_number(parts[38]),
        float_market_value=float_cap_yi * 100_000_000 if float_cap_yi is not None else None,
        vwap=vwap,
        market_time=_parse_market_time(parts[30] if len(parts) > 30 else None),
        received_at=datetime.now(CHINA_TZ),
        source="腾讯行情",
    )


def fetch_eastmoney_quote(code: str) -> Quote:
    code = normalize_code(code)
    fields = "f43,f44,f45,f46,f47,f48,f57,f58,f60,f116,f117,f124,f168"
    payload = _get_json(
        "https://push2.eastmoney.com/api/qt/stock/get",
        {
            "secid": f"0.{code}",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "invt": "2",
            "fltt": "2",
            "fields": fields,
        },
        referer="https://quote.eastmoney.com/",
    )
    row = payload.get("data") or {}
    returned = str(row.get("f57") or "").zfill(6)
    if returned != code:
        raise MarketDataError("东方财富行情未返回该代码")
    volume_lots = _number(row.get("f47"))
    amount = _number(row.get("f48"))
    volume_shares = volume_lots * 100 if volume_lots is not None else None
    vwap = amount / volume_shares if amount and volume_shares else None
    timestamp = _number(row.get("f124"))
    market_time = datetime.fromtimestamp(timestamp, CHINA_TZ) if timestamp else None
    return Quote(
        code=code,
        name=str(row.get("f58") or "").strip(),
        price=_number(row.get("f43")),
        open=_number(row.get("f46")),
        high=_number(row.get("f44")),
        low=_number(row.get("f45")),
        previous_close=_number(row.get("f60")),
        vwap=vwap,
        turnover_pct=_number(row.get("f168")),
        volume_shares=volume_shares,
        amount_yuan=amount,
        float_market_value=_number(row.get("f117")),
        market_time=market_time,
        received_at=datetime.now(CHINA_TZ),
        source="东方财富行情",
    )


def fetch_quote(code: str) -> tuple[Quote, list[str]]:
    errors: list[str] = []
    for fetcher in (fetch_tencent_quote, fetch_eastmoney_quote):
        try:
            return fetcher(code), errors
        except Exception as exc:
            errors.append(f"{fetcher.__name__}: {exc}")
    raise MarketDataError("；".join(errors) or "所有行情源均不可用")


def _profile_from_row(row: dict[str, Any]) -> IpoProfile:
    code = str(row.get("SECURITY_CODE") or "").split(".")[0].zfill(6)
    issue_pe = _number(row.get("AFTER_ISSUE_PE"))
    industry_pe = _number(row.get("INDUSTRY_PE_NEW") or row.get("INDUSTRY_PE"))
    discount = (1 - issue_pe / industry_pe) * 100 if issue_pe is not None and industry_pe else None
    listing = str(row.get("LISTING_DATE") or row.get("SELECT_LISTING_DATE") or "")[:10] or None
    return IpoProfile(
        code=code,
        name=str(row.get("SECURITY_NAME") or row.get("SECURITY_NAME_ABBR") or "").strip(),
        issue_price=_number(row.get("ISSUE_PRICE")),
        issue_pe=issue_pe,
        industry_pe=industry_pe,
        pe_discount_pct=discount,
        industry=str(row.get("INDUSTRY_NAME") or "").strip() or None,
        main_business=str(row.get("MAIN_BUSINESS") or "").strip() or None,
        listing_date=listing,
        subscription_date=str(row.get("APPLY_DATE") or "")[:10] or None,
        issue_shares=_number(row.get("ISSUE_NUM")),
    )


def fetch_ipo_profiles() -> dict[str, IpoProfile]:
    payload = _get_json(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        {
            "sortColumns": "APPLY_DATE,SECURITY_CODE",
            "sortTypes": "-1,-1",
            "pageSize": "1000",
            "pageNumber": "1",
            "reportName": "RPTA_APP_IPOAPPLY",
            "columns": "ALL",
        },
        referer="https://data.eastmoney.com/",
        timeout=12,
    )
    if not payload.get("success"):
        raise MarketDataError(str(payload.get("message") or "发行资料接口不可用"))
    profiles: dict[str, IpoProfile] = {}
    for row in ((payload.get("result") or {}).get("data") or []):
        market = str(row.get("MARKET_TYPE_NEW") or row.get("MARKET_TYPE") or "")
        if market != "北交所":
            continue
        profile = _profile_from_row(row)
        if profile.code.strip("0"):
            profiles[profile.code] = profile
    return profiles


class MarketClient:
    """Small process-local cache so a public deployment does not hammer free endpoints."""

    def __init__(self, quote_ttl: float = 2.5, profile_ttl: float = 900):
        self.quote_ttl = quote_ttl
        self.profile_ttl = profile_ttl
        self._quotes: dict[str, tuple[float, Quote, list[str]]] = {}
        self._profiles: tuple[float, dict[str, IpoProfile]] = (0.0, {})
        self._lock = threading.RLock()

    def quote(self, code: str) -> tuple[Quote, list[str]]:
        code = normalize_code(code)
        now = time.monotonic()
        with self._lock:
            cached = self._quotes.get(code)
            if cached and now - cached[0] <= self.quote_ttl:
                return cached[1], list(cached[2])
        quote, warnings = fetch_quote(code)
        with self._lock:
            self._quotes[code] = (now, quote, warnings)
        return quote, warnings

    def profile(self, code: str) -> IpoProfile | None:
        code = normalize_code(code)
        now = time.monotonic()
        with self._lock:
            cached_at, profiles = self._profiles
            if profiles and now - cached_at <= self.profile_ttl:
                return profiles.get(code)
        profiles = fetch_ipo_profiles()
        with self._lock:
            self._profiles = (now, profiles)
        return profiles.get(code)
