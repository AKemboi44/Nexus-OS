"""The admin page shows whether PayPal is charging real money (live) or test money (sandbox)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import cloud_app
from app.payments.paypal import paypal_status

UI = Path(__file__).resolve().parent.parent / "app" / "admin_ui"
KEYS = ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_MODE", "PAYPAL_WEBHOOK_ID", "PAYPAL_RETURN_URL")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)


def configure(monkeypatch, **env):
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PAYPAL_RETURN_URL", "https://brisklightai.com/")
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_without_credentials_it_says_not_configured():
    status = paypal_status()
    assert status["mode"] == "not_configured" and status["configured"] is False


def test_sandbox_is_the_default_when_credentials_exist(monkeypatch):
    configure(monkeypatch)
    status = paypal_status()
    assert status["mode"] == "sandbox" and status["warnings"] == []


def test_live_with_a_webhook_has_no_warnings(monkeypatch):
    configure(monkeypatch, PAYPAL_MODE="live", PAYPAL_WEBHOOK_ID="WH-1")
    status = paypal_status()
    assert status["mode"] == "live" and status["webhook_configured"] is True and status["warnings"] == []


def test_live_without_a_webhook_is_flagged(monkeypatch):
    configure(monkeypatch, PAYPAL_MODE="LIVE")
    status = paypal_status()
    assert status["mode"] == "live" and any("PAYPAL_WEBHOOK_ID" in w for w in status["warnings"])


def test_an_unrecognised_mode_is_reported_as_live_because_the_client_treats_it_that_way(monkeypatch):
    configure(monkeypatch, PAYPAL_MODE="production", PAYPAL_WEBHOOK_ID="WH-1")
    status = paypal_status()
    assert status["mode"] == "live" and any("production" in w for w in status["warnings"])


def test_a_missing_or_insecure_return_url_is_flagged(monkeypatch):
    configure(monkeypatch, PAYPAL_RETURN_URL="http://localhost:3000/")
    assert any("PAYPAL_RETURN_URL" in w for w in paypal_status()["warnings"])


def test_the_status_agrees_with_the_endpoint_the_client_really_calls(monkeypatch):
    for mode, expected in (("sandbox", "api-m.sandbox.paypal.com"), ("live", "api-m.paypal.com"), ("whatever", "api-m.paypal.com")):
        configure(monkeypatch, PAYPAL_MODE=mode)
        client_url = cloud_app.PayPalClient().base_url
        assert expected in client_url
        assert (paypal_status()["mode"] == "sandbox") == ("sandbox" in client_url)


def test_credentials_never_appear_in_the_status(monkeypatch):
    configure(monkeypatch, PAYPAL_MODE="live", PAYPAL_WEBHOOK_ID="WH-SECRET-ID")
    assert "secret" not in str(paypal_status()) and "WH-SECRET-ID" not in str(paypal_status())


def test_the_endpoint_needs_the_admin_token(monkeypatch):
    monkeypatch.setenv("NEXUS_ADMIN_TOKEN", "t0ken")
    client = TestClient(cloud_app.app)
    assert client.get("/v1/admin/status").status_code == 401
    assert client.get("/v1/admin/status", headers={"X-Admin-Token": "wrong"}).status_code == 401
    configure(monkeypatch, PAYPAL_MODE="live", PAYPAL_WEBHOOK_ID="WH-1")
    body = client.get("/v1/admin/status", headers={"X-Admin-Token": "t0ken"}).json()
    assert body == {"paypal": {"mode": "live", "configured": True, "webhook_configured": True, "warnings": []}}


def test_the_admin_page_shows_a_dot_per_mode_without_inline_code():
    html, js, css = ((UI / name).read_text(encoding="utf-8") for name in ("index.html", "admin.js", "admin.css"))
    assert 'id="modeBadge"' in html and 'id="modeNotice"' in html and "style=" not in html
    assert "/v1/admin/status" in js and "textContent" in js and "innerHTML" not in js
    for mode in ("live", "sandbox", "not_configured"):
        assert f".mode-badge.{mode} .dot" in css
    assert "background: var(--good)" in css.split(".mode-badge.live .dot")[1].split("}")[0], "live is a filled green circle"
    assert "background: transparent" in css.split(".mode-badge.sandbox .dot")[1].split("}")[0], "sandbox is a hollow ring"
    assert "renderMode();" in js and "$('modeNotice').hidden = true" in js


def test_the_status_never_changes_which_environment_is_charged():
    source = (Path(__file__).resolve().parent.parent / "app" / "payments" / "paypal.py").read_text(encoding="utf-8")
    assert source.count('os.getenv("PAYPAL_MODE"') == 2, "client and status read the mode the same way"
