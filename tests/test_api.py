from fastapi.testclient import TestClient

from app import main
from app.market import CHINA_TZ, IpoProfile, MarketDataError, Quote
from app.main import app
from app.store import CloudMarketStore


client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["service"] == "bse-ipo-sell-cloud"


def test_invalid_code_is_rejected_before_network():
    response = client.get("/api/analyze", params={"code": "600000"})
    assert response.status_code == 400
    assert "北交所" in response.json()["detail"]


def test_home_and_static_assets():
    response = client.get("/")
    assert response.status_code == 200
    assert "北交所新股首日卖出助手 V3.2" in response.text
    assert "竞价、换手、VWAP、回撤、临停与盘中存档" in response.text
    assert client.get("/static/app.js").status_code == 200


def test_capacitor_origin_can_call_api():
    response = client.options(
        "/api/analyze?code=920000",
        headers={
            "Origin": "https://localhost",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-App-Token",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://localhost"
    assert "x-app-token" in response.headers["access-control-allow-headers"].lower()


def test_service_worker_is_root_scoped_and_not_cached():
    response = client.get("/service-worker.js")
    assert response.status_code == 200
    assert response.headers["service-worker-allowed"] == "/"
    assert response.headers["cache-control"] == "no-store"
    assert "networkOnly" in response.text


def _pending_profile(listing_date=None):
    return IpoProfile(
        code="920071",
        name="金钛股份",
        issue_price=9.72,
        issue_pe=13.41,
        industry_pe=25.29,
        pe_discount_pct=None,
        industry=None,
        main_business=None,
        listing_date=listing_date,
        subscription_date="2026-08-19",
        issue_shares=45_000_000,
    )


def test_pending_ipo_returns_friendly_message(monkeypatch):
    monkeypatch.setattr(main.market, "profile", lambda code: _pending_profile())
    monkeypatch.setattr(
        main.market,
        "quote",
        lambda code: (_ for _ in ()).throw(MarketDataError("raw provider failure")),
    )

    response = client.get("/api/analyze", params={"code": "920071", "position": 100})

    assert response.status_code == 409
    assert "尚未上市" in response.json()["detail"]
    assert "raw provider failure" not in response.text


def test_future_listing_date_skips_quote(monkeypatch):
    monkeypatch.setattr(main.market, "profile", lambda code: _pending_profile("2999-08-28"))
    monkeypatch.setattr(main.market, "quote", lambda code: (_ for _ in ()).throw(AssertionError("quote should not run")))

    response = client.get("/api/analyze", params={"code": "920071"})

    assert response.status_code == 409
    assert "2999-08-28" in response.json()["detail"]


def test_frontend_hides_stale_dashboard_on_error():
    script = client.get("/static/app.js").text
    assert "function hideDashboard()" in script
    assert "if (response.status === 409)" in script
    assert "state.paused = true;" in script
    assert "scheduleRefresh();" in script


def test_v32_quote_api_persists_turnover_metrics(monkeypatch, tmp_path):
    now = main.datetime.now(CHINA_TZ)
    profile = _pending_profile(now.date().isoformat())
    quote = Quote(
        code="920071", name="金钛股份", price=20, open=19, high=21, low=18.8,
        previous_close=9.72, vwap=19.6, turnover_pct=10,
        volume_shares=1_000_000, amount_yuan=19_600_000,
        float_market_value=500_000_000, market_time=now, received_at=now,
        source="测试行情",
    )
    test_store = CloudMarketStore(f"sqlite:///{(tmp_path / 'api.sqlite3').as_posix()}")
    test_store.save_profile({
        "code": "920071", "issuePrice": 9.72,
        "firstDayTradableShares": 10_000_000,
        "denominatorSource": "上市公告书", "denominatorVerified": True,
    })
    monkeypatch.setattr(main, "store", test_store)
    monkeypatch.setattr(main.market, "profile", lambda code: profile)
    monkeypatch.setattr(main.market, "quote", lambda code: (quote, []))

    response = client.get("/api/quote", params={"code": "920071"})

    assert response.status_code == 200
    payload = response.json()["quote"]
    assert payload["turnover"] == 10
    assert payload["dataQuality"]["denominatorVerified"] is True
    assert payload["dataQuality"]["persistent"] is False


def test_v32_profile_and_signal_archive_api(monkeypatch, tmp_path):
    test_store = CloudMarketStore(f"sqlite:///{(tmp_path / 'archive-api.sqlite3').as_posix()}")
    monkeypatch.setattr(main, "store", test_store)
    monkeypatch.setattr(main.market, "profile", lambda code: _pending_profile("2026-08-25"))
    saved = client.post("/api/profile/save", json={
        "code": "920071", "issuePrice": 9.72,
        "firstDayTradableShares": 45_000_000,
        "denominatorSource": "上市公告书", "denominatorVerified": True,
    })
    event = client.post("/api/signal-event", json={
        "sessionDate": "2026-08-25", "code": "920071",
        "capturedAt": "2026-08-25T09:35:00+08:00", "source": "test",
        "grade": "观察", "nearest": "继续观察", "decisionKey": "hold",
    })
    archive = client.get("/api/signal-events", params={"code": "920071", "date": "2026-08-25"})

    assert saved.status_code == 200
    assert saved.json()["profile"]["denominatorVerified"] is True
    assert event.status_code == 200
    assert archive.json()["archive"]["total"] == 1
