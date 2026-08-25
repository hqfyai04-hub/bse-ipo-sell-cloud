from fastapi.testclient import TestClient

from app import main
from app.market import IpoProfile, MarketDataError
from app.main import app


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
    assert "输入代码，判断当前卖出窗口" in response.text
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
    assert "if (response.status === 409) clearInterval(state.timer);" in script
