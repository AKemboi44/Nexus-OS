"""The /admin dashboard shell: strict CSP, no inline code, no data baked into the page."""

import re
from pathlib import Path

import cloud_app

UI = Path(__file__).resolve().parent.parent / "app" / "admin_ui"


def _client():
    from fastapi.testclient import TestClient
    return TestClient(cloud_app.app)


def test_dashboard_serves_html_with_a_strict_csp():
    response = _client().get("/admin")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/html")
    csp = response.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "style-src 'self'" in csp and "default-src 'none'" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp and "frame-ancestors 'none'" in csp
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex"
    assert _client().get("/admin/").status_code == 200


def test_assets_are_served_with_the_right_types():
    client = _client()
    script, styles = client.get("/admin/admin.js"), client.get("/admin/admin.css")
    assert script.status_code == 200 and "javascript" in script.headers["content-type"]
    assert styles.status_code == 200 and styles.headers["content-type"].startswith("text/css")
    assert script.headers["content-security-policy"] == client.get("/admin").headers["content-security-policy"]


def test_page_has_no_inline_script_or_style():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", html), "inline script would be blocked by the CSP"
    assert "<style" not in html and 'style="' not in html
    assert not re.search(r"\son[a-z]+=", html), "inline event handlers would be blocked"


def test_page_script_never_turns_data_into_markup():
    js = (UI / "admin.js").read_text(encoding="utf-8")
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert forbidden not in js, forbidden
    assert 'style="' not in js and "setAttribute('style'" not in js
    assert "localStorage" not in js, "the admin token must not outlive the tab"
    assert "sessionStorage" in js and "X-Admin-Token" in js


def test_page_holds_no_figures_or_secrets():
    combined = "".join((UI / name).read_text(encoding="utf-8") for name in ("index.html", "admin.js", "admin.css"))
    assert "NEXUS_ADMIN_TOKEN" not in combined
    assert "/v1/admin/metrics" in combined and "/v1/admin/trace/" in combined and "/v1/admin/health" in combined


def test_status_is_never_colour_alone():
    js = (UI / "admin.js").read_text(encoding="utf-8")
    for label in ("On target", "Watch", "Off target", "Low sample", "No data"):
        assert f"label: '{label}'" in js
    assert js.count("glyph:") >= 6, "every status carries a shape glyph as well as a label"
    assert "View as table" in js, "charts have a table view"


def test_the_dashboard_data_still_requires_the_token():
    client = _client()
    assert client.get("/v1/admin/metrics").status_code == 401
    assert client.get("/admin").status_code == 200
