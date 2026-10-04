"""The "Your plan" panel: what the user bought, the balance, and upgrade options that stay available."""

import re
from pathlib import Path

import pytest

from app.payments.catalog import get_pack
from app.payments.checkout import capture_pack_order, create_pack_checkout
from tests.test_checkout import AUTH, BUYER, OTHER, api, pp, store  # noqa: F401 (fixtures)

ROOT = Path(__file__).resolve().parent.parent
WEBSITE_JS = (ROOT / "website" / "app.js").read_text(encoding="utf-8")
WEBSITE_HTML = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
WEBSITE_CSS = (ROOT / "website" / "styles.css").read_text(encoding="utf-8")


def buy(pp, store, pack_id, user=BUYER):
    order = create_pack_checkout(pp, store, user, pack_id)["order_id"]
    pp.approve(order)
    capture_pack_order(pp, store, user, order)
    return order


def entitlement(api, user=BUYER):
    return api.get(f"/v1/entitlements/{user}", headers=AUTH).json()


# --- backend ------------------------------------------------------------------------------------------

def test_a_free_user_has_no_plan(api):
    body = entitlement(api)
    assert body["plan"] is None and body["scans_remaining"] is None


def test_the_plan_names_the_pack_and_the_purchased_total(api, pp, store):
    buy(pp, store, "starter_20")
    plan = entitlement(api)["plan"]
    assert (plan["pack_id"], plan["pack_name"], plan["scans_purchased"]) == ("starter_20", "Starter Pack", 20)
    assert plan["packs"] == [{"name": "Starter Pack", "scans": 20}] and plan["last_purchased_at"]


def test_two_packs_stack_into_one_plan_with_the_latest_name_first(api, pp, store):
    buy(pp, store, "starter_20")
    buy(pp, store, "researcher_50")
    body = entitlement(api)
    assert body["plan"]["scans_purchased"] == 70 and body["scans_remaining"] == 70
    assert body["plan"]["pack_id"] == "researcher_50"
    assert sorted(pack["scans"] for pack in body["plan"]["packs"]) == [20, 50]


def test_the_total_never_falls_below_what_is_left(api, pp, store):
    buy(pp, store, "starter_20")
    with store._connect() as connection:
        connection.execute("UPDATE entitlements SET bundle_queries_remaining = 25 WHERE user_key = ?", (BUYER,))
    assert entitlement(api)["plan"]["scans_purchased"] == 25


def test_a_refunded_pack_leaves_the_plan(api, pp, store):
    kept = buy(pp, store, "starter_20")
    refunded = buy(pp, store, "researcher_50")
    store.refund_pack_order(refunded, get_pack("researcher_50"))
    plan = entitlement(api)["plan"]
    assert plan["scans_purchased"] == 20 and [pack["name"] for pack in plan["packs"]] == ["Starter Pack"]
    assert kept


def test_a_fully_refunded_user_has_no_plan(api, pp, store):
    order = buy(pp, store, "starter_20")
    store.refund_pack_order(order, get_pack("starter_20"))
    assert entitlement(api)["plan"] is None


def test_a_retired_pack_id_is_skipped_instead_of_breaking_the_panel(api, pp, store):
    buy(pp, store, "starter_20")
    with store._connect() as connection:
        connection.execute("UPDATE payment_orders SET pack_id = 'retired_pack' WHERE user_key = ?", (BUYER,))
    assert entitlement(api)["plan"] is None


def test_other_users_purchases_never_appear(api, pp, store):
    buy(pp, store, "starter_20", user=OTHER)
    assert entitlement(api)["plan"] is None
    assert [order["pack_id"] for order in store.purchase_summary(OTHER)] == ["starter_20"]


def test_the_purchase_response_carries_the_plan_too(api, pp):
    created = api.post("/v1/checkout/orders", json={"pack_id": "starter_20"}, headers=AUTH).json()
    pp.approve(created["order_id"])
    result = api.post(f"/v1/checkout/orders/{created['order_id']}/capture", headers=AUTH).json()
    assert result["entitlement"]["plan"]["scans_purchased"] == 20


def test_a_failing_order_lookup_does_not_break_the_entitlement_read(api, pp, store, monkeypatch):
    buy(pp, store, "starter_20")
    monkeypatch.setattr(store, "purchase_summary", lambda user: (_ for _ in ()).throw(RuntimeError("down")))
    body = entitlement(api)
    assert body["plan"] is None and body["active"] is True and body["scans_remaining"] == 20


# --- the panel -------------------------------------------------------------------------------------------

def test_the_plan_panel_exists_above_the_workspace_and_uses_no_inline_styles():
    section = WEBSITE_HTML[WEBSITE_HTML.index('id="planCard"'):]
    section = section[:section.index("</section>")]
    for element in ("planRing", "planRingValue", "planName", "planBalance", "planExpiry", "planNudge", "planAddScans", "planNotice"):
        assert f'id="{element}"' in section, element
    assert 'style="' not in section
    assert WEBSITE_HTML.index('id="planCard"') < WEBSITE_HTML.index('class="workspace-grid"')


def test_the_panel_is_built_from_the_server_plan_with_text_nodes():
    body = WEBSITE_JS[WEBSITE_JS.index("function renderPlan()"):]
    body = body[:body.index("\n    }\n")]
    assert "plan = result.plan || null" in WEBSITE_JS and "renderPlan();" in WEBSITE_JS
    assert "`${left} of ${total} scans left`" in body and "days left" in body
    assert "innerHTML" not in body
    assert "setProperty('--plan-progress'" in body
    for state in ("is-low", "is-empty", "is-expired"):
        assert state in body and f".plan-card.{state}" in WEBSITE_CSS


def test_a_low_balance_turns_the_add_scans_button_into_the_loud_one():
    body = WEBSITE_JS[WEBSITE_JS.index("function renderPlan()"):]
    body = body[:body.index("\n    }\n")]
    assert "left <= LOW_SCANS || percent <= 20" in body
    assert "state ? 'button button-cta' : 'button button-outline'" in body
    assert "byId('planAddScans').addEventListener('click', () => openUpgrade('header'))" in WEBSITE_JS


def test_the_pricing_card_becomes_an_add_more_scans_offer_for_pack_owners():
    assert 'id="pricingTitle"' in WEBSITE_HTML and 'id="pricingLead"' in WEBSITE_HTML
    assert "hasPlan ? 'Add more scans'" in WEBSITE_JS


def test_the_purchase_confirmation_lives_in_the_plan_panel_and_survives_the_pricing_card():
    body = WEBSITE_JS[WEBSITE_JS.index("async function finishCheckout(orderId)"):]
    body = body[:body.index("\n    }\n")]
    assert "setPlanNotice(" in body and "Payment confirmed." in body and "pack.scans" in body
    assert "setMessage(status," not in body, "the pricing card message is the one that used to vanish"
    assert "byId('plansCard').hidden = false" in body, "pricing options stay open after buying"


def test_the_balance_is_refreshed_after_every_scan_and_cleared_on_sign_out():
    scan = WEBSITE_JS[WEBSITE_JS.index("async function runScan(event)"):]
    assert "refreshEntitlement().catch(() => {})" in scan[:scan.index("\n    }\n")]
    out = WEBSITE_JS[WEBSITE_JS.index("async function signOut()"):]
    out = out[:out.index("\n    }\n")]
    assert "plan = null" in out and "scansRemaining = null" in out


@pytest.mark.parametrize("selector", [".plan-card", ".plan-ring", ".plan-nudge", ".plan-card.is-low", ".plan-card.is-empty"])
def test_plan_panel_styles_exist(selector):
    assert selector in WEBSITE_CSS
    assert re.search(r"@media \(max-width: 720px\) \{\s*\.plan-card \{ grid-template-columns: 1fr", WEBSITE_CSS)


def test_the_notice_is_styled_by_id_because_setmessage_rewrites_its_class_name():
    assert "#planNotice { grid-column: 1 / -1" in WEBSITE_CSS and ".plan-notice" not in WEBSITE_CSS
