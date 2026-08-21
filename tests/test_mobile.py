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


def test_capacitor_android_configuration_is_current():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "capacitor.config.json").read_text(encoding="utf-8"))
    gradle = (ROOT / "android" / "variables.gradle").read_text(encoding="utf-8")
    assert package["dependencies"]["@capacitor/android"] == "8.5.0"
    assert config["appId"] == "com.hqfyai.bseiposell"
    assert config["webDir"] == "www"
    assert "minSdkVersion = 24" in gradle
    assert "targetSdkVersion = 36" in gradle
