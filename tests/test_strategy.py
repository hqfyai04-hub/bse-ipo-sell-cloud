from datetime import datetime, timedelta

from app.market import CHINA_TZ, IpoProfile, Quote
from app.strategy import SellWindowEngine


def at(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 8, 20, hour, minute, second, tzinfo=CHINA_TZ)


def profile(listing_date: str = "2026-08-20", issue_price: float = 10) -> IpoProfile:
    return IpoProfile(
        code="920059",
        name="测试新股",
        issue_price=issue_price,
        issue_pe=15,
        industry_pe=30,
        pe_discount_pct=50,
        industry="制造业",
        main_business="测试",
        listing_date=listing_date,
        subscription_date="2026-08-10",
        issue_shares=20_000_000,
    )


def quote(now: datetime, **changes) -> Quote:
    values = {
        "code": "920059",
        "name": "测试新股",
        "price": 21.0,
        "open": 20.0,
        "high": 22.0,
        "low": 19.0,
        "previous_close": 10.0,
        "vwap": 20.5,
        "turnover_pct": 35.0,
        "volume_shares": 7_000_000,
        "amount_yuan": 143_500_000,
        "float_market_value": 420_000_000,
        "market_time": now,
        "received_at": now,
        "source": "测试行情",
    }
    values.update(changes)
    return Quote(**values)


def test_first_five_minutes_are_protected():
    engine = SellWindowEngine()
    now = at(9, 32)
    decision = engine.analyze(
        quote(now, price=19.2, high=21, vwap=20), profile(), position=400, now=now
    )
    assert decision.action == "HOLD"
    assert decision.sell_ratio_pct == 0
    assert "硬保护" in decision.headline


def test_first_minute_failure_trims_multi_lot_but_not_single_lot():
    now = at(9, 31)
    failing = quote(now, price=18, open=20, high=20, low=18, vwap=19.2)
    multi = SellWindowEngine().analyze(failing, profile(), position=400, now=now)
    single = SellWindowEngine().analyze(failing, profile(), position=100, now=now)
    assert multi.sell_ratio_pct == 50
    assert multi.sell_quantity == 200
    assert single.sell_ratio_pct == 0
    assert "单手" in single.headline


def test_opening_spike_fade_and_single_lot_conversion():
    now = at(9, 49)
    fading = quote(now, price=20.5, open=20, high=22, vwap=21)
    multi = SellWindowEngine().analyze(fading, profile(issue_price=8), position=1000, now=now)
    single = SellWindowEngine().analyze(fading, profile(issue_price=8), position=100, now=now)
    assert multi.sell_ratio_pct == 70
    assert "尖峰回落" in multi.headline
    assert single.sell_ratio_pct == 100


def test_vwap_sustained_double_break_exits():
    engine = SellWindowEngine()
    first = at(9, 40)
    weak = quote(first, price=19.2, open=20, high=20.5, vwap=19.6)
    initial = engine.analyze(weak, profile(), position=400, now=first)
    assert initial.sell_ratio_pct in {0, 50}

    later = first + timedelta(minutes=6)
    weak.market_time = later
    weak.volume_shares = 7_200_000
    weak.amount_yuan = 145_000_000
    confirmed = engine.analyze(weak, profile(), position=400, now=later)
    assert confirmed.sell_ratio_pct == 100
    assert "双破" in confirmed.headline


def test_secondary_breakout_uses_five_percent_trailing_exit():
    engine = SellWindowEngine()
    before_freeze = at(9, 44)
    engine.analyze(
        quote(before_freeze, price=30.8, open=29, high=31, vwap=30),
        profile(issue_price=20), position=400, now=before_freeze,
    )
    breakout_time = at(9, 46)
    engine.analyze(
        quote(breakout_time, price=31.5, open=29, high=31.5, vwap=30.5),
        profile(issue_price=20), position=400, now=breakout_time,
    )
    fade_time = at(9, 50)
    result = engine.analyze(
        quote(fade_time, price=29.8, open=29, high=31.5, vwap=30.2),
        profile(issue_price=20), position=400, now=fade_time,
    )
    assert result.sell_ratio_pct == 100
    assert "二次突破" in result.headline


def test_tail_time_rule_and_non_listing_day_gate():
    now = at(14, 46)
    exit_decision = SellWindowEngine().analyze(quote(now), profile(), position=300, now=now)
    wrong_day = SellWindowEngine().analyze(
        quote(now), profile(listing_date="2026-08-19"), position=300, now=now
    )
    assert exit_decision.sell_ratio_pct == 100
    assert wrong_day.action == "NOT_APPLICABLE"
    assert wrong_day.sell_ratio_pct == 0


def test_stale_live_quote_suspends_strong_signal():
    now = at(10, 0)
    old = now - timedelta(seconds=30)
    decision = SellWindowEngine().analyze(
        quote(old, price=18, open=20, high=22, vwap=20), profile(), position=400, now=now
    )
    assert decision.action == "VERIFY"
    assert decision.sell_ratio_pct == 0
