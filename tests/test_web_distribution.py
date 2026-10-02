import json
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

from app.agents.scribe_agent import ReportSynthesisError, ScribeResearchAgent


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


def test_website_surfaces_exports_library_controls_and_email_only_signin():
    website = ROOT / "website"
    html = (website / "index.html").read_text(encoding="utf-8")
    js = (website / "app.js").read_text(encoding="utf-8")
    css = (website / "styles.css").read_text(encoding="utf-8")

    assert 'id="googleSignIn"' not in html
    assert "Download Excel dossier" in html
    assert "Download proposal report" in html
    assert 'id="historySearch"' in html
    assert 'id="historyDateFilter"' in html
    assert "LIBRARY_PAGE_SIZE = 5" in js
    assert "HISTORY_PAGE_SIZE = 3" in js
    assert "filteredRuns.slice(historyPage * HISTORY_PAGE_SIZE, (historyPage + 1) * HISTORY_PAGE_SIZE)" in js
    assert "Free accounts can choose up to 3 criteria. Upgrade to select up to 5." in js
    assert "function displayName(email)" in js
    assert "mailto:support@brisklightai.com" in js
    assert "WhatsApp support is coming soon" in js
    assert "prefers-reduced-motion: reduce" in css
    assert ".status-callout.success" in css
    assert 'id="includedPagination"' in html
    assert 'id="excludedPagination"' in html
    assert "RESULT_PAGE_SIZE = 3" in js
    assert ".library-page-button:hover:not(:disabled)" in css
    assert ".library-page-button:focus-visible" in css
    assert "function renderEvidencePage(included)" in js
    assert "sources.slice(start, start + RESULT_PAGE_SIZE)" in js
    assert "function cleanDisplayedSourceText(text)" in js
    assert "cleanDisplayedSourceText(source.abstract).slice(0, 380)" in js
    assert "cleanDisplayedSourceText(source.abstract).slice(0, 240)" in js


def test_scan_results_show_prominent_source_totals_and_capitalize_topic():
    website = ROOT / "website"
    html = (website / "index.html").read_text(encoding="utf-8")
    js = (website / "app.js").read_text(encoding="utf-8")
    css = (website / "styles.css").read_text(encoding="utf-8")

    for count_id in ("reviewedCount", "includedCount", "excludedCount"):
        assert f'id="{count_id}"' in html
    assert "Sources Reviewed" in html
    assert "Sources Included" in html
    assert "Sources Filtered Out" in html
    assert "resultIncludedSources.length + resultExcludedSources.length" in js
    assert "if (counter) counter.textContent = String(count)" in js
    assert "if (resultSummary)" in js
    assert "topic[0].toLocaleUpperCase() + topic.slice(1)" in js
    assert ".reviewed-stat strong" in css
    assert ".included-stat strong" in css
    assert ".filtered-stat strong" in css
    assert ".result-stat { flex-wrap: nowrap;" in css
    assert 'href="/styles.css?v=20261002-4"' in html
    assert 'src="/app.js?v=20261002-5"' in html
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in css


def test_website_revalidates_html_to_avoid_mixed_cached_scan_assets():
    website = ROOT / "website"
    headers = (website / "_headers").read_text(encoding="utf-8")

    assert "/index.html\n  Cache-Control: no-cache, no-store, must-revalidate" in headers
    assert "/\n  Cache-Control: no-cache, no-store, must-revalidate" in headers


def test_website_includes_original_section_art_and_visible_background_motion():
    website = ROOT / "website"
    css = (website / "styles.css").read_text(encoding="utf-8")

    for asset in ("evidence-network.svg", "research-layers.svg"):
        image = website / "images" / asset
        assert image.is_file()
        assert image.read_text(encoding="utf-8").startswith("<svg")
        assert f"/images/{asset}" in css
    assert "hero-art-drift" in css
    assert "section-art-drift" in css
    assert "prefers-reduced-motion: reduce" in css


def test_generated_report_without_referenceable_sources_fails_closed():
    with tempfile.TemporaryDirectory() as output_directory:
        with pytest.raises(ReportSynthesisError, match="requires sources"):
            ScribeResearchAgent().generate_apa_dossier_report(
                topic="Evidence based testing",
                included_sources=[],
                output_directory=output_directory,
            )

    assert not list(Path(output_directory).glob("*.docx"))
