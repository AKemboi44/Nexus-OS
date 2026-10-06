"""Who may open the admin dashboard: the shared token, or an allow-listed account that passed two-factor sign-in."""

import base64
import json

import pytest

import cloud_app

ENDPOINT = "/v1/admin/status"


def _client():
    from fastapi.testclient import TestClient
    return TestClient(cloud_app.app)


def _jwt(aal):
    def segment(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    return f"{segment({'alg': 'HS256'})}.{segment({'aal': aal})}.signature"


def _sign_in(monkeypatch, email, confirmed=True):
    user = {"id": "user-id", "email": email}
    if confirmed:
        user["email_confirmed_at"] = "2026-01-01T00:00:00Z"
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: user)


def _bearer(aal):
    return {"Authorization": f"Bearer {_jwt(aal)}"}


@pytest.fixture(autouse=True)
def _admin_env(monkeypatch):
    monkeypatch.setenv("NEXUS_ADMIN_TOKEN", "admin-secret")
    monkeypatch.delenv("NEXUS_ADMIN_EMAILS", raising=False)


def test_allow_listed_account_with_two_factor_is_admitted(monkeypatch):
    _sign_in(monkeypatch, "akiptoo20@gmail.com")
    assert _client().get(ENDPOINT, headers=_bearer("aal2")).status_code == 200


def test_email_match_ignores_case_and_spacing(monkeypatch):
    _sign_in(monkeypatch, " AkIpToO20@Gmail.com ")
    assert _client().get(ENDPOINT, headers=_bearer("aal2")).status_code == 200


def test_password_only_session_is_refused_until_two_factor_passes(monkeypatch):
    _sign_in(monkeypatch, "akiptoo20@gmail.com")
    response = _client().get(ENDPOINT, headers=_bearer("aal1"))
    assert response.status_code == 403
    assert response.json()["detail"] == "Two-factor authentication required."


def test_token_without_an_assurance_claim_is_refused(monkeypatch):
    _sign_in(monkeypatch, "akiptoo20@gmail.com")
    assert _client().get(ENDPOINT, headers={"Authorization": "Bearer not-a-jwt"}).status_code == 403


def test_other_accounts_are_refused_even_with_two_factor(monkeypatch):
    for email in ("hildakiptoo97@gmail.com", "someone@example.com"):
        _sign_in(monkeypatch, email)
        assert _client().get(ENDPOINT, headers=_bearer("aal2")).status_code == 403


def test_unconfirmed_email_is_refused(monkeypatch):
    _sign_in(monkeypatch, "akiptoo20@gmail.com", confirmed=False)
    assert _client().get(ENDPOINT, headers=_bearer("aal2")).status_code == 403


def test_admin_emails_variable_replaces_the_default(monkeypatch):
    monkeypatch.setenv("NEXUS_ADMIN_EMAILS", "new.admin@example.com, second@example.com")
    _sign_in(monkeypatch, "second@example.com")
    assert _client().get(ENDPOINT, headers=_bearer("aal2")).status_code == 200
    _sign_in(monkeypatch, "akiptoo20@gmail.com")
    assert _client().get(ENDPOINT, headers=_bearer("aal2")).status_code == 403


def test_shared_token_still_works_and_a_wrong_one_does_not():
    assert _client().get(ENDPOINT, headers={"X-Admin-Token": "admin-secret"}).status_code == 200
    assert _client().get(ENDPOINT, headers={"X-Admin-Token": "wrong"}).status_code == 401


def test_no_credential_is_unauthorized():
    assert _client().get(ENDPOINT).status_code == 401


def test_every_dashboard_endpoint_uses_the_guard(monkeypatch):
    _sign_in(monkeypatch, "someone@example.com")
    for path in ("/v1/admin/analytics", "/v1/admin/metrics", "/v1/admin/health", "/v1/admin/status",
                 "/v1/admin/trace/trace-12345678", "/v1/admin/metrics/anything", "/v1/analytics/ab-conversion"):
        assert _client().get(path, headers=_bearer("aal2")).status_code == 403, path


def test_entitlements_reports_admin_flag(monkeypatch):
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    for email, expected in (("akiptoo20@gmail.com", True), ("someone@example.com", False)):
        monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization, email=email: {
            "id": "user-id", "email": email, "email_confirmed_at": "2026-01-01T00:00:00Z",
        })
        response = _client().get("/v1/entitlements/user-id", headers={"Authorization": "Bearer x"})
        assert response.status_code == 200 and response.json()["is_admin"] is expected
