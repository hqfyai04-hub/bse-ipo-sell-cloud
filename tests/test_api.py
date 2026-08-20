from fastapi.testclient import TestClient

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
