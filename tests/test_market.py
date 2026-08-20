from datetime import datetime

from app import market


def test_normalize_code():
    assert market.normalize_code("BJ 920059") == "920059"


def test_parse_tencent_quote(monkeypatch):
    parts = [""] * 52
    parts[1] = "测试新股"
    parts[2] = "920059"
    parts[3] = "20.50"
    parts[4] = "11.13"
    parts[5] = "19.00"
    parts[30] = "20260820094105"
    parts[33] = "22.00"
    parts[34] = "18.80"
    parts[36] = "120000"
    parts[37] = "24660"
    parts[38] = "37.13"
    parts[44] = "6.62"
    parts[51] = "20.55"
    payload = f'v_bj920059="{"~".join(parts)}";'.encode("gbk")
    monkeypatch.setattr(market, "_get_bytes", lambda *args, **kwargs: payload)

    quote = market.fetch_tencent_quote("920059")

    assert quote.code == "920059"
    assert quote.name == "测试新股"
    assert quote.volume_shares == 12_000_000
    assert quote.amount_yuan == 246_600_000
    assert quote.float_market_value == 662_000_000
    assert quote.market_time == datetime(2026, 8, 20, 9, 41, 5, tzinfo=market.CHINA_TZ)


def test_profile_mapping():
    profile = market._profile_from_row(
        {
            "SECURITY_CODE": "920059",
            "SECURITY_NAME": "测试新股",
            "ISSUE_PRICE": "10",
            "AFTER_ISSUE_PE": "15",
            "INDUSTRY_PE_NEW": "30",
            "INDUSTRY_NAME": "制造业",
            "MAIN_BUSINESS": "测试业务",
            "LISTING_DATE": "2026-08-20 00:00:00",
            "APPLY_DATE": "2026-08-10",
            "ISSUE_NUM": "20000000",
        }
    )
    assert profile.code == "920059"
    assert profile.pe_discount_pct == 50
    assert profile.listing_date == "2026-08-20"
