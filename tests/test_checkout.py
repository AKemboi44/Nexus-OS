"""Pack checkout: server-priced orders, verified capture, idempotent credit, webhooks, refunds."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

import cloud_app
from app.payments import checkout, paypal as paypal_module
from app.payments.catalog import default_pack, get_pack, money
from app.payments.checkout import CheckoutError, capture_pack_order, create_pack_checkout, handle_paypal_event
from app.payments.entitlements import EntitlementStore, parse_time
from app.payments.paypal import PayPalClient, PayPalError

PACK = default_pack()
BUYER, OTHER = "user-buyer", "user-other"


class FakePayPal:
    """Stands in for PayPal: orders must be approved before they can be captured."""

    def __init__(self):
        self.orders = {}
        self.capture_calls = 0
        self.verify_result = True
        self.verify_error = None

    def create_pack_order(self, pack, user_id, invoice_id):
        order_id = f"ORDER{len(self.orders) + 1:06d}"
        self.orders[order_id] = {"pack": pack, "user": user_id, "approved": False, "invoice": invoice_id}
        return {"id": order_id, "status": "CREATED",
                "links": [{"rel": "payer-action", "href": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}"}]}

    def approval_url(self, order):
        return PayPalClient.approval_url(order)

    def approve(self, order_id):
        self.orders[order_id]["approved"] = True

    def capture_order(self, order_id):
        self.capture_calls += 1
        order = self.orders[order_id]
        if not order["approved"]:
            raise PayPalError(422, "UNPROCESSABLE_ENTITY", "not approved", ["ORDER_NOT_APPROVED"])
        pack = order["pack"]
        capture = {
            "id": f"CAP-{order_id}", "status": order.get("capture_status", "COMPLETED"),
            "amount": {"currency_code": order.get("currency", pack.currency), "value": order.get("charged", pack.price_text)},
            "custom_id": order.get("custom", order["user"]),
        }
        return {"id": order_id, "status": "COMPLETED",
                "purchase_units": [{"custom_id": order["user"], "payments": {"captures": [capture]}}]}

    def verify_webhook_signature(self, headers, event):
        if self.verify_error:
            raise self.verify_error
        return self.verify_result


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr("app.payments.entitlements.SupabaseRestClient.from_env", lambda: None)
    return EntitlementStore(str(tmp_path / "entitlements.sqlite3"))


@pytest.fixture
def pp():
    return FakePayPal()


def buy(pp, store, user=BUYER, approve=True):
    started = create_pack_checkout(pp, store, user, None)
    if approve:
        pp.approve(started["order_id"])
    return started["order_id"]


def approved_event(order_id, event_id="EVT-APPROVED"):
    return {"id": event_id, "event_type": "CHECKOUT.ORDER.APPROVED", "resource": {"id": order_id}}


def capture_event(order_id, amount=None, event_id="EVT-CAPTURE", status="COMPLETED", user=BUYER):
    return {"id": event_id, "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {
        "id": f"CAP-{order_id}", "status": status, "custom_id": user,
        "amount": {"currency_code": "USD", "value": amount or PACK.price_text},
        "supplementary_data": {"related_ids": {"order_id": order_id}}}}


def refund_event(order_id, amount=None, event_id="EVT-REFUND"):
    return {"id": event_id, "event_type": "PAYMENT.CAPTURE.REFUNDED", "resource": {
        "id": "REFUND-1", "amount": {"currency_code": "USD", "value": amount or PACK.price_text},
        "links": [{"rel": "up", "href": f"https://api.sandbox.paypal.com/v2/payments/captures/CAP-{order_id}"}]}}


# --- catalog and order creation ------------------------------------------------------------

def test_the_price_comes_from_the_catalog_and_is_normalised():
    assert PACK.price == Decimal("10.00") and PACK.scans == 20 and PACK.validity_days == 90
    assert money(10) == money("10.0") == money(10.00) == Decimal("10.00")
    assert get_pack("no-such-pack") is None and get_pack(None) == PACK and get_pack(PACK.id) == PACK


def test_creating_a_checkout_records_a_pending_order_at_the_catalog_price(pp, store):
    started = create_pack_checkout(pp, store, BUYER, None)

    order = store.get_order(started["order_id"])
    assert (order["status"], order["user_id"], order["amount"], order["currency"]) == ("pending", BUYER, PACK.price, "USD")
    assert started["approve_url"].startswith("https://www.sandbox.paypal.com/")
    assert started["pack"]["price"] == "10.00" and started["pack"]["scans"] == 20
    assert pp.orders[started["order_id"]]["pack"] == PACK


def test_an_unknown_pack_is_rejected_before_calling_paypal(pp, store):
    with pytest.raises(CheckoutError) as error:
        create_pack_checkout(pp, store, BUYER, "free-money")
    assert error.value.status_code == 400 and pp.orders == {}


def test_the_approval_link_must_be_https_on_paypal():
    good = {"links": [{"rel": "payer-action", "href": "https://www.paypal.com/checkoutnow?token=A"}]}
    assert PayPalClient.approval_url(good).startswith("https://www.paypal.com/")
    for href in ("http://www.paypal.com/x", "https://paypal.com.evil.test/x", "https://evil.test/paypal.com"):
        with pytest.raises(PayPalError):
            PayPalClient.approval_url({"links": [{"rel": "approve", "href": href}]})


# --- capture --------------------------------------------------------------------------------

def test_a_verified_capture_credits_the_pack_once(pp, store):
    order_id = buy(pp, store)

    result = capture_pack_order(pp, store, BUYER, order_id)

    assert result.status == "credited" and result.credited_now
    record = store.get(BUYER)
    assert record["status"] == "ACTIVE" and record["bundle_queries_remaining"] == PACK.scans and record["plan"] == PACK.id
    assert abs(parse_time(record["ends_at"]) - (datetime.now(timezone.utc) + timedelta(days=90))) < timedelta(minutes=1)
    assert store.is_active(BUYER) is True
    assert store.get_order(order_id)["status"] == "credited"


def test_repeating_the_capture_never_credits_twice(pp, store):
    order_id = buy(pp, store)
    capture_pack_order(pp, store, BUYER, order_id)

    again = capture_pack_order(pp, store, BUYER, order_id)

    assert again.status == "already_credited" and not again.credited_now
    assert store.get(BUYER)["bundle_queries_remaining"] == PACK.scans
    assert pp.capture_calls == 1, "a credited order is answered without calling PayPal again"


def test_another_user_cannot_capture_someone_elses_order(pp, store):
    order_id = buy(pp, store)
    with pytest.raises(CheckoutError) as error:
        capture_pack_order(pp, store, OTHER, order_id)
    assert error.value.status_code == 404 and store.get(OTHER) is None and store.get(BUYER) is None


def test_an_unapproved_order_cannot_be_captured(pp, store):
    order_id = buy(pp, store, approve=False)
    with pytest.raises(PayPalError):
        capture_pack_order(pp, store, BUYER, order_id)
    assert store.get(BUYER) is None and store.get_order(order_id)["status"] == "pending"


@pytest.mark.parametrize("tamper", [{"charged": "1.00"}, {"currency": "EUR"}, {"custom": "someone-else"}])
def test_a_payment_that_does_not_match_the_order_is_never_credited(pp, store, tamper):
    order_id = buy(pp, store)
    pp.orders[order_id].update(tamper)

    with pytest.raises(CheckoutError) as error:
        capture_pack_order(pp, store, BUYER, order_id)

    assert error.value.code == "payment_mismatch"
    assert store.get(BUYER) is None and store.get_order(order_id)["status"] == "pending"


def test_a_pending_capture_waits_for_the_webhook(pp, store):
    order_id = buy(pp, store)
    pp.orders[order_id]["capture_status"] = "PENDING"

    result = capture_pack_order(pp, store, BUYER, order_id)
    assert result.status == "pending" and store.get(BUYER) is None
    assert store.get_order(order_id)["status"] == "captured"

    settled = handle_paypal_event(pp, store, capture_event(order_id))
    assert settled.status == "credited" and store.get(BUYER)["bundle_queries_remaining"] == PACK.scans


# --- webhooks -------------------------------------------------------------------------------

def test_the_approved_webhook_credits_a_buyer_who_closed_the_tab(pp, store):
    order_id = buy(pp, store)

    result = handle_paypal_event(pp, store, approved_event(order_id))
    assert result.status == "credited" and store.get(BUYER)["bundle_queries_remaining"] == PACK.scans

    later = capture_pack_order(pp, store, BUYER, order_id)  # the buyer finally returns
    assert later.status == "already_credited" and store.get(BUYER)["bundle_queries_remaining"] == PACK.scans


def test_the_capture_completed_webhook_is_idempotent_after_a_credit(pp, store):
    order_id = buy(pp, store)
    capture_pack_order(pp, store, BUYER, order_id)
    assert handle_paypal_event(pp, store, capture_event(order_id)).status == "already_credited"
    assert store.get(BUYER)["bundle_queries_remaining"] == PACK.scans


def test_a_webhook_amount_mismatch_is_rejected(pp, store):
    order_id = buy(pp, store)
    with pytest.raises(CheckoutError):
        handle_paypal_event(pp, store, capture_event(order_id, amount="0.01"))
    assert store.get(BUYER) is None


def test_unknown_and_subscription_events_are_ignored_not_guessed_at(pp, store):
    assert handle_paypal_event(pp, store, {"id": "E1", "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
                                           "resource": {"id": "I-1"}}).status == "ignored"
    assert handle_paypal_event(pp, store, approved_event("ORDER-NOT-OURS")).status == "ignored"


def test_an_event_is_final_only_after_it_was_processed(store):
    assert store.begin_event("EVT-1") is True
    assert store.begin_event("EVT-1") is True, "an unfinished event stays retryable"
    store.finish_event("EVT-1")
    assert store.begin_event("EVT-1") is False, "a processed event is not run twice"


# --- refunds --------------------------------------------------------------------------------

def test_a_full_refund_revokes_the_pack_and_is_idempotent(pp, store):
    order_id = buy(pp, store)
    capture_pack_order(pp, store, BUYER, order_id)

    assert handle_paypal_event(pp, store, refund_event(order_id)).status == "refunded"
    record = store.get(BUYER)
    assert record["status"] == "CANCELLED" and record["bundle_queries_remaining"] == 0
    assert store.is_active(BUYER) is False and store.get_order(order_id)["status"] == "refunded"

    assert handle_paypal_event(pp, store, refund_event(order_id, event_id="EVT-REFUND-2")).status == "ignored"


def test_a_partial_refund_does_not_revoke_access(pp, store):
    order_id = buy(pp, store)
    capture_pack_order(pp, store, BUYER, order_id)
    result = handle_paypal_event(pp, store, refund_event(order_id, amount="5.00"))
    assert result.status == "ignored" and store.is_active(BUYER) is True


def test_a_reversal_revokes_the_pack(pp, store):
    order_id = buy(pp, store)
    capture_pack_order(pp, store, BUYER, order_id)
    event = {"id": "EVT-REV", "event_type": "PAYMENT.CAPTURE.REVERSED", "resource": {"id": f"CAP-{order_id}", "amount": {"value": PACK.price_text}}}
    assert handle_paypal_event(pp, store, event).status == "refunded"
    assert store.is_active(BUYER) is False


def test_a_denied_capture_closes_a_pending_order(pp, store):
    order_id = buy(pp, store)
    event = {"id": "EVT-DENIED", "event_type": "PAYMENT.CAPTURE.DENIED", "resource": {
        "id": "CAP-X", "supplementary_data": {"related_ids": {"order_id": order_id}}}}
    assert handle_paypal_event(pp, store, event).status == "failed"
    assert store.get_order(order_id)["status"] == "failed"
    with pytest.raises(CheckoutError):
        capture_pack_order(pp, store, BUYER, order_id)


# --- entitlement behaviour ---------------------------------------------------------------------

def test_buying_again_stacks_scans_and_extends_validity(pp, store):
    capture_pack_order(pp, store, BUYER, buy(pp, store))
    capture_pack_order(pp, store, BUYER, buy(pp, store))

    record = store.get(BUYER)
    assert record["bundle_queries_remaining"] == 2 * PACK.scans
    assert abs(parse_time(record["ends_at"]) - (datetime.now(timezone.utc) + timedelta(days=180))) < timedelta(minutes=1)


def test_an_unlimited_subscriber_keeps_unlimited_access(pp, store):
    store.upsert(BUYER, "paypal", "I-SUB-1", "ACTIVE", plan="pro")
    result = capture_pack_order(pp, store, BUYER, buy(pp, store))

    assert result.status == "credited" and result.detail.get("unlimited") is True
    record = store.get(BUYER)
    assert record["provider"] == "paypal" and record["bundle_queries_remaining"] is None


def test_an_expired_pack_is_no_longer_active(store):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    store.upsert(BUYER, "pack", "pack_old", "ACTIVE", plan=PACK.id, ends_at=past)
    assert store.is_active(BUYER) is False
    assert store.check_query_permission(BUYER)["tier"] == "free"


def test_an_exhausted_pack_keeps_download_access_until_it_expires(pp, store):
    capture_pack_order(pp, store, BUYER, buy(pp, store))
    for _ in range(PACK.scans):
        store.increment_query_usage(BUYER)

    permission = store.check_query_permission(BUYER)
    assert permission["allowed"] is False and permission["reason"] == "bundle_queries_exhausted"
    assert store.is_active(BUYER) is True


# --- Supabase: payments must fail loudly, never fall back to the local file -------------------------

def _supabase_store(tmp_path, monkeypatch, client):
    monkeypatch.setattr("app.payments.entitlements.SupabaseRestClient.from_env", lambda: client)
    return EntitlementStore(str(tmp_path / "local.sqlite3"))


def test_a_supabase_failure_is_raised_not_written_to_the_local_file(tmp_path, monkeypatch):
    client = MagicMock()
    client.insert.side_effect = RuntimeError("Supabase database request failed.")
    client.request.side_effect = RuntimeError("Supabase database request failed.")
    store = _supabase_store(tmp_path, monkeypatch, client)

    with pytest.raises(RuntimeError):
        store.create_order("ORDER000001", BUYER, PACK)
    with pytest.raises(RuntimeError):
        store.credit_pack_order({"order_id": "ORDER000001", "user_id": BUYER}, PACK, "CAP-1")
    import sqlite3
    local = sqlite3.connect(str(tmp_path / "local.sqlite3"))
    assert local.execute("SELECT COUNT(*) FROM payment_orders").fetchone()[0] == 0
    assert local.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0] == 0


def test_the_credit_goes_to_the_atomic_database_function(tmp_path, monkeypatch):
    client = MagicMock()
    client.request.return_value = {"credited": True, "scans_added": 10}
    store = _supabase_store(tmp_path, monkeypatch, client)

    result = store.credit_pack_order({"order_id": "ORDER000001", "user_id": BUYER}, PACK, "CAP-1")

    assert result == {"credited": True, "scans_added": 10}
    method, resource = client.request.call_args.args[:2]
    assert (method, resource) == ("POST", "rpc/nexus_credit_pack")
    assert client.request.call_args.kwargs["json"] == {
        "p_order_id": "ORDER000001", "p_user_id": BUYER, "p_pack_id": PACK.id,
        "p_scans": PACK.scans, "p_validity_days": 90, "p_capture_id": "CAP-1"}


def test_the_migration_defines_the_functions_the_code_calls():
    from pathlib import Path
    sql = (Path(__file__).resolve().parent.parent / "supabase" / "migrations"
           / "202610040001_payment_orders_and_pack_credit.sql").read_text(encoding="utf-8")
    for needle in ("create table if not exists public.payment_orders",
                   "function public.nexus_credit_pack", "function public.nexus_refund_pack",
                   "p_order_id text", "p_user_id uuid", "p_pack_id text", "p_scans integer",
                   "p_validity_days integer", "p_capture_id text", "processed_at timestamptz",
                   "status in ('pending', 'captured')", "for update"):
        assert needle in sql, needle


# --- PayPalClient over mocked HTTP --------------------------------------------------------------------

class Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body if body is not None else {}
        self.ok = status < 400
        self.content = json.dumps(self._body).encode()

    def json(self):
        return self._body

    def raise_for_status(self):
        pass


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "secret")
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    calls = []
    script = []
    monkeypatch.setattr(paypal_module.requests, "post", lambda *a, **k: Resp(200, {"access_token": "tok"}))

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        return script.pop(0)

    monkeypatch.setattr(paypal_module.requests, "request", fake_request)
    return calls, script


def test_the_order_request_carries_the_server_price_and_the_buyer(http):
    calls, script = http
    script.append(Resp(201, {"id": "O1", "links": []}))
    PayPalClient().create_pack_order(PACK, BUYER, "NX-INVOICE")

    method, url, body = calls[0]
    unit = body["purchase_units"][0]
    assert (method, url) == ("POST", "https://api-m.sandbox.paypal.com/v2/checkout/orders")
    assert unit["amount"] == {"currency_code": "USD", "value": PACK.price_text}
    assert unit["custom_id"] == BUYER and unit["invoice_id"] == "NX-INVOICE" and body["intent"] == "CAPTURE"


def test_capturing_an_already_captured_order_returns_its_details(http):
    calls, script = http
    script.append(Resp(422, {"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "ORDER_ALREADY_CAPTURED"}]}))
    script.append(Resp(200, {"id": "O1", "status": "COMPLETED"}))

    assert PayPalClient().capture_order("ORDER000001")["status"] == "COMPLETED"
    assert [c[0] for c in calls] == ["POST", "GET"]


def test_other_paypal_errors_surface_with_their_codes(http):
    _, script = http
    script.append(Resp(422, {"name": "UNPROCESSABLE_ENTITY", "message": "no", "details": [{"issue": "ORDER_NOT_APPROVED"}]}))
    with pytest.raises(PayPalError) as error:
        PayPalClient().capture_order("ORDER000001")
    assert error.value.status_code == 422 and error.value.issues == ["ORDER_NOT_APPROVED"]


def test_order_ids_are_validated_before_use():
    for bad in ("", "../etc", "a b", "x" * 200):
        with pytest.raises(ValueError):
            PayPalClient().get_order(bad)


# --- HTTP endpoints ----------------------------------------------------------------------------------------

@pytest.fixture
def api(pp, store, monkeypatch):
    from fastapi.testclient import TestClient
    events = []
    monkeypatch.setattr(cloud_app, "paypal", pp)
    monkeypatch.setattr(cloud_app, "entitlements", store)
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": BUYER, "email": "buyer@example.com"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app.analytics, "record", lambda **event: events.append(event))
    client = TestClient(cloud_app.app)
    client.events = events
    return client


AUTH = {"Authorization": "Bearer token"}


def named(client, name):
    return [e for e in client.events if e["event_name"] == name]


def test_the_pack_on_sale_is_public_and_matches_the_catalog(api):
    body = api.get("/v1/checkout/pack").json()
    assert body["price"] == PACK.price_text and body["scans"] == PACK.scans and body["id"] == PACK.id


def test_creating_and_capturing_over_http_credits_once_and_reports_revenue_once(api, pp):
    created = api.post("/v1/checkout/orders", json={}, headers=AUTH).json()
    assert created["approve_url"].startswith("https://www.sandbox.paypal.com/")
    assert named(api, "checkout_started")[0]["properties"]["order_id"] == created["order_id"]
    pp.approve(created["order_id"])

    first = api.post(f"/v1/checkout/orders/{created['order_id']}/capture", headers=AUTH).json()
    second = api.post(f"/v1/checkout/orders/{created['order_id']}/capture", headers=AUTH).json()

    assert first["status"] == "credited" and second["status"] == "already_credited"
    assert first["entitlement"] == {**first["entitlement"], "active": True, "scans_remaining": PACK.scans}
    assert len(named(api, "payment_completed")) == 1 and len(named(api, "bundle_purchased")) == 1
    assert named(api, "bundle_purchased")[0]["properties"]["price"] == float(PACK.price)
    assert all("_schema_problems" not in e["properties"] and "_unregistered" not in e["properties"] for e in api.events)


def test_the_client_cannot_choose_the_price(api, pp):
    response = api.post("/v1/checkout/orders", json={"pack_id": PACK.id, "price": "0.01", "amount": "0.01"}, headers=AUTH)
    assert response.status_code == 200
    order = pp.orders[response.json()["order_id"]]
    assert order["pack"].price_text == PACK.price_text
    assert api.post("/v1/checkout/orders", json={"pack_id": "nope"}, headers=AUTH).status_code == 400


def test_paypal_outages_become_honest_errors_and_a_payment_failed_event(api, pp, monkeypatch):
    monkeypatch.setattr(pp, "create_pack_order", lambda *a: (_ for _ in ()).throw(PayPalError(500, "INTERNAL", "boom")))
    response = api.post("/v1/checkout/orders", json={}, headers=AUTH)
    assert response.status_code == 502 and response.json()["detail"]["error_code"] == "paypal_error"
    assert named(api, "payment_failed")[0]["properties"]["error_code"] == "PAYPAL_API_ERROR"

    monkeypatch.setattr(pp, "create_pack_order", lambda *a: (_ for _ in ()).throw(RuntimeError("PayPal credentials are not configured on the server.")))
    assert api.post("/v1/checkout/orders", json={}, headers=AUTH).status_code == 503


def test_old_subscription_and_plan_endpoints_are_gone(api):
    for path in ("/v1/paypal/orders", "/v1/paypal/subscriptions", "/v1/paypal/capture"):
        assert api.post(path, json={"plan": "pro"}, headers=AUTH).status_code in (404, 405), path


def post_webhook(api, event):
    return api.post("/v1/paypal/webhook", json=event)


def test_webhook_rejects_a_bad_signature_and_reports_missing_configuration(api, pp):
    pp.verify_result = False
    assert post_webhook(api, approved_event("O1")).status_code == 400
    pp.verify_error = RuntimeError("PAYPAL_WEBHOOK_ID is not configured.")
    assert post_webhook(api, approved_event("O1")).status_code == 503


def test_webhook_credits_then_ignores_a_replay(api, pp, store):
    order_id = buy(pp, store)
    first = post_webhook(api, approved_event(order_id))
    replay = post_webhook(api, approved_event(order_id))

    assert first.json() == {"status": "processed", "outcome": "credited"}
    assert replay.json() == {"status": "already_processed"}
    assert store.get(BUYER)["bundle_queries_remaining"] == PACK.scans
    assert len(named(api, "payment_completed")) == 1


def test_a_failed_webhook_is_retried_by_paypal_and_then_succeeds(api, pp, store, monkeypatch):
    order_id = buy(pp, store)
    real_capture = pp.capture_order
    monkeypatch.setattr(pp, "capture_order", lambda oid: (_ for _ in ()).throw(PayPalError(503, "UNAVAILABLE", "")))
    failed = post_webhook(api, approved_event(order_id))
    assert failed.status_code == 500 and store.get(BUYER) is None

    monkeypatch.setattr(pp, "capture_order", real_capture)
    retried = post_webhook(api, approved_event(order_id))
    assert retried.status_code == 200 and retried.json()["outcome"] == "credited"
    assert store.get(BUYER)["bundle_queries_remaining"] == PACK.scans


def test_a_rejected_payment_is_acknowledged_so_paypal_stops_retrying(api, pp, store):
    order_id = buy(pp, store)
    response = post_webhook(api, capture_event(order_id, amount="0.01"))
    assert response.status_code == 200 and response.json() == {"status": "rejected", "code": "payment_mismatch"}
    assert post_webhook(api, capture_event(order_id, amount="0.01")).json() == {"status": "already_processed"}
    assert store.get(BUYER) is None


# --- clients: one truthful, server-driven checkout ---------------------------------------------------------

def _read(*parts):
    from pathlib import Path
    return (Path(__file__).resolve().parent.parent.joinpath(*parts)).read_text(encoding="utf-8")


def test_website_checks_out_through_the_new_endpoints_and_says_one_time():
    js, html = _read("website", "app.js"), _read("website", "index.html")
    assert "/v1/checkout/orders" in js and "/capture" in js and "/v1/checkout/packs" in js
    assert "/v1/paypal/subscriptions" not in js and "/v1/paypal/capture" not in js
    assert 'id="pricingGrid"' in html and "data-plan" not in html and 'id="buyPack"' not in html
    assert "/ month" not in html and "monthly billing" not in html and "Research Ultimate" not in html
    assert "one-time" in html.lower() and "NO SUBSCRIPTION" in html
    assert "JSON.stringify({pack_id: packId})" in js, "the buyer names a pack; the server decides the price"


def test_website_return_url_triggers_a_server_side_capture_not_just_a_message():
    js = _read("website", "app.js")
    assert "checkoutResult === 'complete' && returnedOrder" in js
    assert "await finishCheckout(returnedOrder)" in js
    assert "history.replaceState" in js, "the order token must not stay in the address bar"


def test_extension_uses_the_pack_checkout_and_no_subscription_wording():
    js, html = _read("extension", "popup.js"), _read("extension", "popup.html")
    assert "/v1/checkout/orders" in js and "/v1/checkout/packs" in js and "order.approve_url" in js
    assert "/v1/paypal/subscriptions" not in js and "selectedPlan" not in js
    assert "pack_id: selectedPack()?.id" in js
    for stale in ("$19", "$49", "/ month", "per month", "renews monthly", "Research Ultimate", "subscription plans"):
        assert stale not in html, stale
    assert 'id="packOptions"' in html and "does not renew" in html
