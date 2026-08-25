import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as image:
        assert image.read(8) == b"\x89PNG\r\n\x1a\n"
        length = struct.unpack(">I", image.read(4))[0]
        assert image.read(4) == b"IHDR"
        assert length >= 8
        return struct.unpack(">II", image.read(8))


def test_pwa_manifest_and_icons_are_installable():
    manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    assert manifest["start_url"].startswith("/")
    sizes = {icon["sizes"]: icon for icon in manifest["icons"]}
    for expected in (192, 512):
        icon = sizes[f"{expected}x{expected}"]
        path = STATIC / icon["src"].removeprefix("/static/")
        assert png_size(path) == (expected, expected)


def test_service_worker_never_caches_live_api():
    worker = (STATIC / "service-worker.js").read_text(encoding="utf-8")
    assert 'url.pathname.startsWith("/api/")' in worker
    assert "networkOnly(event.request)" in worker


def test_token_fragment_is_saved_locally_then_removed_from_address():
    app_script = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'launchParams.get("token")' in app_script
    assert 'localStorage.setItem("bseAccessToken", launchToken)' in app_script
    assert 'history.replaceState(null, "", `${location.pathname}${location.search}`)' in app_script


def test_position_field_accepts_100_shares_and_odd_lots():
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="position"' in index
    assert 'step="100" value="100"' in index


def test_refresh_can_be_paused_and_resumed():
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="autoBtn"' in index
    assert '$("autoBtn").textContent="启动自动行情"' in index
    assert '$("autoBtn").textContent="停止自动行情"' in index


def test_capacitor_android_configuration_is_current():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "capacitor.config.json").read_text(encoding="utf-8"))
    gradle = (ROOT / "android" / "variables.gradle").read_text(encoding="utf-8")
    assert package["dependencies"]["@capacitor/android"] == "8.5.0"
    assert config["appId"] == "com.hqfyai.bseiposell"
    assert config["webDir"] == "www"
    assert "minSdkVersion = 24" in gradle
    assert "targetSdkVersion = 36" in gradle
