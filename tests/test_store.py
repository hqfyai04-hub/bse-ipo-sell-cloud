from datetime import datetime, timedelta

from app.market import CHINA_TZ
from app.store import CloudMarketStore


def test_profile_snapshot_metrics_and_reopen(tmp_path):
    url = f"sqlite:///{(tmp_path / 'market.sqlite3').as_posix()}"
    store = CloudMarketStore(url)
    store.save_profile({
        "code": "920059",
        "issuePrice": 10,
        "firstDayTradableShares": 10_000_000,
        "denominatorSource": "上市公告书",
        "denominatorVerified": True,
    })
    start = datetime(2026, 8, 20, 9, 25, 20, tzinfo=CHINA_TZ)
    first = store.record_snapshot({
        "code": "920059", "source": "test", "price": 20,
        "open": 20, "high": 20, "low": 20, "vwap": 20,
        "volumeShares": 500_000, "amountYuan": 10_000_000,
    }, start)
    store.record_snapshot({
        "code": "920059", "source": "test", "price": 21,
        "open": 20, "high": 21, "low": 20, "vwap": 20.5,
        "volumeShares": 800_000, "amountYuan": 16_400_000,
    }, start + timedelta(minutes=5))

    assert first["customTurnoverPct"] == 5
    assert store.metrics("920059", "2026-08-20")["checkpoints"]["auction_0925"]["turnoverPct"] == 5
    assert store.metrics("920059", "2026-08-20")["turnoverDelta5Pct"] == 3

    reopened = CloudMarketStore(url)
    assert reopened.get_profile("920059")["denominatorVerified"] is True
    assert reopened.metrics("920059", "2026-08-20")["latestCapturedAt"] is not None


def test_signal_archive_marks_material_changes(tmp_path):
    store = CloudMarketStore(f"sqlite:///{(tmp_path / 'signals.sqlite3').as_posix()}")
    base = {
        "sessionDate": "2026-08-20", "code": "920059", "source": "test",
        "price": 20, "high": 21, "vwap": 20.2, "turnoverPct": 10,
        "grade": "观察", "sellRatio": 0, "sellQty": 0,
        "nearest": "继续观察", "decisionKey": "hold", "analysis": [], "state": {},
    }
    first = store.record_signal_event({**base, "capturedAt": "2026-08-20T09:35:00+08:00"})
    second = store.record_signal_event({**base, "capturedAt": "2026-08-20T09:35:05+08:00"})
    third = store.record_signal_event({
        **base, "capturedAt": "2026-08-20T09:35:10+08:00",
        "decisionKey": "sell", "sellRatio": 50, "sellQty": 200,
    })
    archive = store.signal_events("920059", "2026-08-20")

    assert first["isMaterialChange"] is True
    assert second["isMaterialChange"] is False
    assert third["isMaterialChange"] is True
    assert archive["total"] == 3
    assert archive["materialChanges"] == 2
