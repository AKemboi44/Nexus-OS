import json
import struct
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chrome_extension_release_package_contains_manifest_assets():
    subprocess.run(
        [sys.executable, "extension/build_release.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    manifest = json.loads((ROOT / "extension/manifest.json").read_text(encoding="utf-8"))
    package = ROOT / "extension/dist" / f"nexus-research-ai-{manifest['version']}.zip"
    expected_files = {
        "manifest.json",
        "popup.html",
        "popup.js",
        "auth.js",
        *(f"icons/icon-{size}.png" for size in (16, 32, 48, 128)),
    }

    with zipfile.ZipFile(package) as archive:
        assert set(archive.namelist()) == expected_files
        packaged_manifest = json.loads(archive.read("manifest.json"))
        assert packaged_manifest["manifest_version"] == 3
        for size in (16, 32, 48, 128):
            image = archive.read(f"icons/icon-{size}.png")
            assert image.startswith(b"\x89PNG\r\n\x1a\n")
            width, height = struct.unpack(">II", image[16:24])
            assert (width, height) == (size, size)
        assert not any(name.endswith((".env", ".pyc")) for name in archive.namelist())


def test_website_is_static_and_uses_existing_authenticated_services():
    website = ROOT / "website"
    app_js = (website / "app.js").read_text(encoding="utf-8")
    headers = (website / "_headers").read_text(encoding="utf-8")
    redirects = (website / "_redirects").read_text(encoding="utf-8")

    assert "https://nexus-os-production-2e14.up.railway.app" in app_js
    assert "https://mdjgrtkjjcwmhuhpsjsk.supabase.co" in app_js
    assert "/v1/scan" in app_js
    assert "/v1/reports" in app_js
    assert "/v1/research" in app_js
    assert "frame-ancestors 'none'" in headers
    assert "/privacy /privacy.html 200" in redirects
    assert "/terms /terms.html 200" in redirects
    assert (website / "privacy.html").is_file()
    assert (website / "terms.html").is_file()
