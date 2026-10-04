"""The pack lineup ($10 Starter, $19 Researcher, Lab/Team by contact) and the pricing UI that sells it."""

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

import cloud_app
from app.payments.catalog import all_packs, build_catalog, default_pack, get_pack
from app.payments.checkout import CheckoutError, capture_pack_order, create_pack_checkout
from tests.test_checkout import BUYER, api, named, pp, store  # noqa: F401 (fixtures)
from tests.test_metrics_catalog import measure, row

ROOT = Path(__file__).resolve().parent.parent
WEBSITE_JS = (ROOT / "website" / "app.js").read_text(encoding="utf-8")
WEBSITE_HTML = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
WEBSITE_CSS = (ROOT / "website" / "styles.css").read_text(encoding="utf-8")
EXTENSION_JS = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")

AUTH = {"Authorization": "Bearer token"}


# --- catalog -----------------------------------------------------------------------------------

def test_default_lineup_is_starter_then_researcher():
    starter, researcher = all_packs()
    assert (starter.id, starter.price, starter.scans) == ("starter_20", Decimal("10.00"), 20)
    assert (researcher.id, researcher.price, researcher.scans) == ("researcher_50", Decimal("19.00"), 50)
    assert (starter.per_scan_text, researcher.per_scan_text) == ("0.50", "0.38")
    assert starter.badge and researcher.badge == "Best value"
    assert default_pack() == starter and get_pack(None) == starter
    assert all(pack.validity_days == 90 and pack.currency == "USD" for pack in (starter, researcher))


def test_a_bigger_pack_is_always_cheaper_per_scan():
    starter, researcher = all_packs()
    assert researcher.price / researcher.scans < starter.price / starter.scans


def test_unknown_pack_ids_are_not_sellable():
    assert get_pack("lab_team") is None and get_pack("starter_20; drop") is None


def test_the_second_pack_is_tunable_from_the_environment(monkeypatch):
    monkeypatch.setenv("NEXUS_RESEARCHER_PRICE_USD", "24.50")
    monkeypatch.setenv("NEXUS_RESEARCHER_SCANS", "60")
    pack = get_pack("researcher_50")
    assert pack.price == Decimal("24.50") and pack.scans == 60


def _json_catalog(entries):
    return json.dumps(entries)


def test_a_valid_json_override_replaces_the_whole_catalog(monkeypatch):
    monkeypatch.setenv("NEXUS_PACKS_JSON", _json_catalog([
        {"id": "kes_pack", "name": "Student Pack", "price": "7.50", "scans": 12, "badge": "Student price"},
        {"id": "lab_pack", "name": "Lab Pack", "price": 59, "scans": 200, "validity_days": 180},
    ]))
    first, second = all_packs()
    assert (first.id, first.price, first.scans, first.validity_days) == ("kes_pack", Decimal("7.50"), 12, 90)
    assert (second.id, second.price, second.validity_days) == ("lab_pack", Decimal("59.00"), 180)
    assert get_pack("starter_20") is None and default_pack() == first


@pytest.mark.parametrize("raw", [
    "not json", "{}", "[]", _json_catalog([{"id": "x", "name": "x", "price": "0", "scans": 5}]),
    _json_catalog([{"id": "x", "name": "x", "price": "5", "scans": 0}]),
    _json_catalog([{"id": "bad id!", "name": "x", "price": "5", "scans": 5}]),
    _json_catalog([{"id": "a", "name": "x", "price": "5", "scans": 5}, {"id": "a", "name": "y", "price": "6", "scans": 6}]),
    _json_catalog([{"id": f"p{i}", "name": "x", "price": "5", "scans": 5} for i in range(7)]),
    _json_catalog([{"id": "a", "name": "x", "scans": 5}]),
])
def test_an_invalid_override_falls_back_to_the_default_lineup(monkeypatch, raw):
    monkeypatch.setenv("NEXUS_PACKS_JSON", raw)
    assert [pack.id for pack in all_packs()] == ["starter_20", "researcher_50"]


def test_public_view_carries_what_the_pricing_cards_render():
    public = get_pack("researcher_50").public()
    assert public == {**public, "price": "19.00", "scans": 50, "per_scan": "0.38", "badge": "Best value",
                      "currency": "USD", "validity_days": 90}


# --- endpoints and checkout ----------------------------------------------------------------------

def test_the_pack_list_endpoint_returns_both_packs_and_the_default(api):
    body = api.get("/v1/checkout/packs").json()
    assert [p["id"] for p in body["packs"]] == ["starter_20", "researcher_50"] and body["default"] == "starter_20"
    assert api.get("/v1/checkout/pack").json()["id"] == "starter_20", "older clients still get the default pack"


@pytest.mark.parametrize("pack_id", ["starter_20", "researcher_50"])
def test_each_pack_is_charged_and_credited_exactly_as_listed(api, pp, store, pack_id):
    pack = get_pack(pack_id)
    created = api.post("/v1/checkout/orders", json={"pack_id": pack_id}, headers=AUTH).json()
    assert created["pack"]["id"] == pack_id and created["pack"]["price"] == pack.price_text
    assert pp.orders[created["order_id"]]["pack"] == pack
    pp.approve(created["order_id"])

    result = api.post(f"/v1/checkout/orders/{created['order_id']}/capture", headers=AUTH).json()

    assert result["entitlement"]["scans_remaining"] == pack.scans
    purchase = named(api, "bundle_purchased")[0]["properties"]
    assert purchase["bundle_id"] == pack_id and purchase["price"] == float(pack.price)


def test_buying_two_different_packs_stacks_their_scans(pp, store):
    for pack_id in ("starter_20", "researcher_50"):
        order = create_pack_checkout(pp, store, BUYER, pack_id)["order_id"]
        pp.approve(order)
        capture_pack_order(pp, store, BUYER, order)
    assert store.get(BUYER)["bundle_queries_remaining"] == 70


def test_an_unlisted_pack_cannot_be_bought(pp, store):
    with pytest.raises(CheckoutError) as error:
        create_pack_checkout(pp, store, BUYER, "lab_team")
    assert error.value.status_code == 400 and pp.orders == {}


def test_revenue_is_reported_per_pack():
    rows = [row("bundle_purchased", user="a", bundle_id="starter_20", price=10.0),
            row("bundle_purchased", user="b", bundle_id="starter_20", price=10.0),
            row("bundle_purchased", user="c", bundle_id="researcher_50", price=19.0)]
    result = measure(rows, "revenue_total")
    assert result["value"] == 39.0
    assert result["breakdown"]["by_pack"] == {
        "starter_20": {"purchases": 2, "revenue": 20.0}, "researcher_50": {"purchases": 1, "revenue": 19.0}}


# --- the pricing UI --------------------------------------------------------------------------------

def test_the_website_renders_a_card_per_pack_from_the_server_list():
    assert "/v1/checkout/packs" in WEBSITE_JS and "pack.per_scan" in WEBSITE_JS
    assert "packs.map((pack, index) => pricingCard(pack, index === 0))" in WEBSITE_JS
    assert "`Just $${pack.per_scan} per scan`" in WEBSITE_JS
    assert "`Valid for ${pack.validity_days} days`" in WEBSITE_JS
    for hard_coded in ("$10", "$19", "20 scans", "50 scans"):
        assert hard_coded not in WEBSITE_JS and hard_coded not in WEBSITE_HTML, f"price data must come from the server: {hard_coded}"


def test_the_team_card_is_contact_only_and_never_purchasable():
    block = WEBSITE_JS[WEBSITE_JS.index("function teamCard()"):WEBSITE_JS.index("function renderPricing()")]
    assert "data-pack" not in block and "dataset.pack" not in block
    assert "contact.dataset.contact = 'true'" in block and "Contact us" in block
    assert "placement: 'pricing_contact'" in WEBSITE_JS and "byId('contact').scrollIntoView" in WEBSITE_JS
    for promise in ("seats", "shared pool", "SSO", "invoice"):
        assert promise not in block, f"the team card must not promise {promise}: it is not built"


def test_checkout_needs_the_terms_box_and_explains_what_to_do():
    body = WEBSITE_JS[WEBSITE_JS.index("async function startPackCheckout(packId)"):]
    body = body[:body.index("\n    }\n")]
    assert "!byId('billingConsent').checked" in body and "byId('billingConsent').focus()" in body
    assert "pack_id: packId" in body and "#pricingGrid button[data-pack]" in body


def test_the_pricing_section_is_hard_to_miss_and_accessible():
    for needle in (".pricing-hero", ".pricing-card.featured", ".pricing-price .amount", ".button-cta",
                   ".sticky-upgrade", ".upgrade-banner", "linear-gradient"):
        assert needle in WEBSITE_CSS, needle
    assert re.search(r"\.pricing-price \.amount \{[^}]*font-size: 52px", WEBSITE_CSS)
    assert ".button-cta:focus-visible" in WEBSITE_CSS and "prefers-reduced-motion" in WEBSITE_CSS
    assert "@media (max-width: 900px)" in WEBSITE_CSS, "cards stack on small screens"
    assert 'style="' not in WEBSITE_HTML.split('id="plansCard"')[1].split("</section>")[0]


def test_a_sticky_upgrade_bar_is_offered_to_free_users_with_results_on_small_screens():
    assert 'id="stickyUpgrade"' in WEBSITE_HTML and "openUpgrade('sticky_mobile')" in WEBSITE_JS
    assert "bar.hidden = paid || !session || !activeResult" in WEBSITE_JS
    assert ".sticky-upgrade:not([hidden])" in WEBSITE_CSS and "@media (max-width: 720px)" in WEBSITE_CSS


def test_the_banner_and_upsell_quote_the_starting_price_from_the_catalog():
    assert "from ${from}" in WEBSITE_JS and "Packs start at ${formatPrice(starter.price)}" in WEBSITE_JS
    assert "Unlock the full Excel dossier and Word report${priceText}. One payment, no subscription." in WEBSITE_JS


def test_the_extension_lets_the_buyer_choose_a_pack():
    assert "/v1/checkout/packs" in EXTENSION_JS and "function renderPackOptions()" in EXTENSION_JS
    assert "selectedPackId = option.dataset.pack" in EXTENSION_JS and "pack_id: selectedPack()?.id" in EXTENSION_JS
    assert "Just $${pack.per_scan} per scan" in EXTENSION_JS


def test_a_failed_price_load_never_leaves_the_pricing_card_on_loading():
    body = WEBSITE_JS[WEBSITE_JS.index("async function loadPackInfo()"):]
    body = body[:body.index("\n    }\n")]
    assert "if (!response.ok) throw" in body and "if (!response.ok) return" not in body
    assert body.index("catch (error)") < body.index("renderPricing();"), "the grid is re-rendered on failure too"
    assert "'Try again'" in WEBSITE_JS and "if (!packs.length) loadPackInfo();" in WEBSITE_JS
