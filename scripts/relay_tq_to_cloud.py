"""Relay the local V3.2 bridge's verified TQ snapshot to the cloud service.

Usage (run on the Windows PC that has 通达信/TQ):
  python scripts/relay_tq_to_cloud.py --code 920071 --cloud https://... --token ...
"""

from __future__ import annotations

import argparse
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_json(url: str, *, payload: dict | None = None, token: str = "") -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-App-Token"] = token
    with urlopen(Request(url, data=body, headers=headers), timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="将本机TQ只读行情安全中转到V3.2云端助手")
    parser.add_argument("--code", required=True, help="6位北交所证券代码")
    parser.add_argument("--cloud", required=True, help="云端根地址，例如 https://bse-ipo-sell-cloud.onrender.com")
    parser.add_argument("--token", required=True, help="云端 APP_ACCESS_TOKEN")
    parser.add_argument("--local", default="http://127.0.0.1:8765", help="本地V3.2行情桥地址")
    parser.add_argument("--local-token", default="", help="本地行情桥口令（如已启用）")
    parser.add_argument("--interval", type=float, default=2.0, help="中转间隔秒数")
    args = parser.parse_args()

    code = "".join(ch for ch in args.code if ch.isdigit())
    if len(code) != 6:
        raise SystemExit("证券代码必须为6位数字")
    local_query = {"code": code, "force": "1"}
    if args.local_token:
        local_query["token"] = args.local_token
    local_url = f"{args.local.rstrip('/')}/api/quote?{urlencode(local_query)}"
    cloud_url = f"{args.cloud.rstrip('/')}/api/relay/quote"

    print(f"正在中转 {code}：{args.local} → {args.cloud}")
    while True:
        try:
            result = request_json(local_url)
            quote = result.get("quote") or {}
            quality = quote.get("dataQuality") or {}
            if not result.get("ok"):
                raise RuntimeError(result.get("error") or "本地行情不可用")
            if not quality.get("tqPrimary"):
                raise RuntimeError("本地TQ尚未就绪；拒绝把公开备用行情伪装成TQ中转")
            request_json(cloud_url, payload=quote, token=args.token)
            print(f"{quote.get('marketTimestamp') or quote.get('capturedAt')} TQ中转成功", flush=True)
        except Exception as exc:
            print(f"TQ中转等待：{exc}", flush=True)
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    main()
