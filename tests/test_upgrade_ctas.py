"""Upgrade button placements: registered, tracked, measurable, and truthful about the product."""

import re
from pathlib import Path

import pytest

from app.analytics import schema
from app.payments.config import default_pricing_config
from tests.test_metrics_catalog import measure, row

ROOT = Path(__file__).resolve().parent.parent
WEBSITE_JS = (ROOT / "website" / "app.js").read_text(encoding="utf-8")
WEBSITE_HTML = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
EXTENSION_JS = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")
PLACEMENTS = set(schema.get("upgrade_cta_clicked").props["placement"].values)


def test_the_cta_event_is_registered_for_both_clients():
    spec = schema.get("upgrade_cta_clicked")
    assert {schema.WEB, schema.EXTENSION} <= set(spec.sources) and spec.stage == "monetization"
    assert schema.validate("upgrade_cta_clicked", {"placement": "scan_limit"}, schema.WEB) == []
    assert "bad_type:placement" in schema.validate("upgrade_cta_clicked", {"placement": "anywhere"}, schema.WEB)
    assert "missing_prop:placement" in schema.validate("upgrade_cta_clicked", {}, schema.WEB)


def test_every_website_placement_is_registered_and_the_key_ones_exist():
    used = set(re.findall(r"openUpgrade\('([a-z_]+)'\)", WEBSITE_JS)) | set(re.findall(r"placement: '([a-z_]+)'", WEBSITE_JS))
    assert used <= PLACEMENTS, used - PLACEMENTS
    assert {"scan_limit", "results_banner", "deliverables", "report_locked", "excel_quota", "header"} <= used


def test_every_extension_placement_is_registered_and_each_entry_point_reports_one():
    used = set(re.findall(r"openUpgradeFlow\('([a-z_]+)'\)", EXTENSION_JS))
    assert used <= PLACEMENTS, used - PLACEMENTS
    assert {"extension_tile", "extension_banner", "extension_report", "extension_dossier", "extension_scan_limit"} <= used
    for line in EXTENSION_JS.splitlines():
        if "addEventListener('click'" in line and "showUpgradeFlow('details')" in line:
            assert "backToUpgradeDetailsBtn" in line, f"an upgrade button that does not record a placement: {line.strip()}"


def test_the_header_button_is_not_hidden_for_pack_buyers_who_ran_out_of_scans():
    body = WEBSITE_JS[WEBSITE_JS.index("function updateUpgradeButton()"):]
    body = body[:body.index("\n    }\n")]
    assert "paid && scansRemaining === 0" in body and "Buy more scans" in body
    assert "button.hidden = !session || (paid && !exhausted)" in body


def test_paid_users_never_see_sales_prompts_and_the_locked_report_stays_visible():
    body = WEBSITE_JS[WEBSITE_JS.index("function renderUpsells("):]
    body = body[:body.index("\n    }\n")]
    assert "banner.hidden = upsell.hidden = paid" in body
    assert "byId('fullReport').hidden = !paid" not in WEBSITE_JS, "free users must see the premium report as a locked upsell"
    assert "openUpgrade('report_locked')" in WEBSITE_JS


def test_prompts_are_built_safely_with_the_real_price():
    assert "container.replaceChildren(title, text, button)" in WEBSITE_JS
    assert "title.textContent = headline" in WEBSITE_JS and "text.textContent = description" in WEBSITE_JS
    assert "`Unlock from ${from}`" in WEBSITE_JS, "buttons show the real starting price from the catalog"
    for element in ("scanUpgrade", "reportUpgrade", "upgradeBanner", "deliverablesUpsell"):
        assert f'id="{element}"' in WEBSITE_HTML


def test_paywall_copy_names_the_product_that_is_actually_sold():
    texts = " ".join([
        default_pricing_config.bundle_name, default_pricing_config.bundle_description,
        default_pricing_config.paywall_headline, default_pricing_config.paywall_description,
    ])
    assert "Research Pack" in texts
    sources = "".join((ROOT / path).read_text(encoding="utf-8")
                      for path in ("app/payments/config.py", "app/payments/entitlements.py", "cloud_app.py"))
    assert "Review Bundle" not in sources and "Literature Review Bundle" not in sources


# --- metrics ---------------------------------------------------------------------------------------------------

def test_cta_click_rate_counts_clickers_among_scanners_and_breaks_down_by_placement():
    rows = [row("scan_started", user=u, run_id=f"r-{u}") for u in ("a", "b", "c", "d")]
    rows += [row("upgrade_cta_clicked", user="a", source="web", placement="scan_limit"),
             row("upgrade_cta_clicked", user="a", source="web", placement="header"),
             row("upgrade_cta_clicked", user="b", source="web", placement="scan_limit"),
             row("upgrade_cta_clicked", user="x", source="web", placement="header")]  # never scanned
    result = measure(rows, "upgrade_cta_click_rate")

    assert result["value"] == 0.5 and result["numerator"] == 2 and result["denominator"] == 4
    assert result["breakdown"]["clicks_by_placement"] == {"scan_limit": 2, "header": 2}
    assert result["breakdown"]["unique_users_by_placement"] == {"scan_limit": 2, "header": 2}


def test_click_to_checkout_conversion():
    rows = [row("upgrade_cta_clicked", user=u, source="web", placement="header") for u in ("a", "b", "c", "d")]
    rows += [row("checkout_started", user="a"), row("checkout_started", user="b"), row("checkout_started", user="z")]
    result = measure(rows, "cta_to_checkout")
    assert result["value"] == 0.5 and result["denominator"] == 4


def test_cta_metrics_report_no_data_instead_of_zero_when_nothing_happened():
    assert measure([], "upgrade_cta_click_rate")["value"] is None
    assert measure([], "cta_to_checkout")["value"] is None
    assert measure([row("scan_started", user="a", run_id="r")], "upgrade_cta_click_rate")["value"] == 0.0


def test_the_extension_has_a_scan_limit_button():
    html = (ROOT / "extension" / "popup.html").read_text(encoding="utf-8")
    assert 'id="upgradeFromScanBtn"' in html
    assert "data.status_code === 403 ? 'block' : 'none'" in EXTENSION_JS
    assert "upgradeFromScanBtn.style.display = 'none'" in EXTENSION_JS, "stale button must clear when a new scan starts"
