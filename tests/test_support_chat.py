"""WhatsApp click-to-chat support: one number, safe links, tracked clicks, and a CSP that still holds."""

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

from app.analytics import schema
from tests.test_metrics_catalog import measure, row

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    "index": ROOT / "website" / "index.html", "terms": ROOT / "website" / "terms.html",
    "privacy": ROOT / "website" / "privacy.html", "app": ROOT / "website" / "app.js",
    "css": ROOT / "website" / "styles.css", "headers": ROOT / "website" / "_headers",
    "popup_html": ROOT / "extension" / "popup.html", "popup_js": ROOT / "extension" / "popup.js",
}
TEXT = {name: path.read_text(encoding="utf-8") for name, path in FILES.items()}
NUMBER = "254743852707"
ANCHOR = re.compile(r"<a\b[^>]*wa\.me[^>]*>", re.I)


def whatsapp_anchors(name):
    return ANCHOR.findall(TEXT[name])


def function_body(source, signature):
    body = source[source.index(signature):]
    return body[:body.index("\n    }\n")]


def test_the_number_is_always_in_international_form():
    for name, text in TEXT.items():
        assert "0743852707" not in text.replace(NUMBER, ""), f"{name} uses the local format"
    assert "+254 743 852 707" in TEXT["terms"] and "+254 743 852 707" in TEXT["privacy"]


@pytest.mark.parametrize("page", ["index", "terms", "privacy", "popup_html"])
def test_every_whatsapp_link_is_safe_and_points_at_the_support_number(page):
    anchors = whatsapp_anchors(page)
    assert anchors, f"{page} has no WhatsApp link"
    for tag in anchors:
        href = re.search(r'href="([^"]+)"', tag).group(1)
        assert href.startswith(f"https://wa.me/{NUMBER}?text="), href
        assert 'target="_blank"' in tag and 'rel="noopener noreferrer"' in tag, tag
        assert "@" not in unquote(href), "prefilled text must not contain an email address"


@pytest.mark.parametrize("page", ["index", "terms", "privacy"])
def test_the_floating_button_is_on_every_page_and_needs_no_script(page):
    assert TEXT[page].count('class="whatsapp-float"') == 1
    tag = next(t for t in whatsapp_anchors(page) if "whatsapp-float" in t)
    assert 'aria-label="Chat with support on WhatsApp"' in tag and "onclick" not in tag and "style=" not in tag


def test_the_placeholder_is_gone_and_the_contact_section_has_a_real_link():
    assert "coming soon" not in TEXT["index"].lower() and "whatsappHint" not in TEXT["index"]
    section = TEXT["index"][TEXT["index"].index('id="contact"'):]
    assert 'data-support="contact"' in section[:1200]


def test_one_support_email_is_used_everywhere():
    for name in ("index", "terms", "privacy", "app", "popup_html", "popup_js"):
        assert "support@brisklightai.com" not in TEXT[name], name
    assert "mailto:brisklightke@gmail.com" in TEXT["terms"] and "mailto:brisklightke@gmail.com" in TEXT["privacy"]


def test_the_floating_button_clears_the_mobile_sticky_bar_and_stays_readable():
    css = TEXT["css"]
    assert ".sticky-upgrade:not([hidden]) ~ .whatsapp-float" in css
    assert "background: #0b7a3e" in css, "white text on WhatsApp's light green fails contrast; the dark green passes"
    assert "z-index: 9" in css.split(".whatsapp-float {")[1].split("}")[0], "below the sign-in dialog (z-index 10)"
    assert ".auth-backdrop { position: fixed; z-index: 10" in css
    assert ".whatsapp-float:focus-visible" in css


def test_the_floating_button_follows_the_sticky_bar_in_the_markup_so_the_sibling_rule_works():
    html = TEXT["index"]
    assert html.index('id="stickyUpgrade"') < html.index('class="whatsapp-float"')


def test_support_links_carry_context_but_no_personal_data():
    body = function_body(TEXT["app"], "function supportLink(context)")
    assert "encodeURIComponent" in body and "email" not in body.lower()
    assert "supportLink(`an error (reference ID" in TEXT["app"] and "setPlanHelp(`my payment (PayPal order" in TEXT["app"]
    assert "innerHTML" not in TEXT["app"][TEXT["app"].index("help.className = 'status-help'"):][:400]


def test_clicks_are_tracked_from_every_support_link():
    assert "closest('a[data-support]')" in TEXT["app"] and "track('support_chat_clicked'" in TEXT["app"]
    assert "sendAnalytics('support_chat_clicked'" in TEXT["popup_js"]
    placements = schema.get("support_chat_clicked").props["placement"].values
    for placement in re.findall(r'data-support="([a-z_]+)"', TEXT["index"] + TEXT["popup_html"]):
        assert placement in placements, placement
    assert "help.dataset.support = 'report_error'" in TEXT["app"]


def test_the_event_is_registered_for_both_clients():
    spec = schema.get("support_chat_clicked")
    assert {schema.WEB, schema.EXTENSION} <= set(spec.sources)
    assert schema.validate("support_chat_clicked", {"placement": "floating"}, schema.WEB) == []
    assert "bad_type:placement" in schema.validate("support_chat_clicked", {"placement": "elsewhere"}, schema.WEB)
    assert "missing_prop:placement" in schema.validate("support_chat_clicked", {}, schema.EXTENSION)


def test_cloudflare_analytics_is_allowed_and_nothing_else_is_loosened():
    csp = next(line for line in TEXT["headers"].splitlines() if "Content-Security-Policy" in line)
    parts = [d.strip() for d in csp.split(":", 1)[1].split(";") if d.strip()]
    directives = {d.split(" ", 1)[0]: d.split(" ", 1)[1] for d in parts}
    assert directives["script-src"] == "'self' https://static.cloudflareinsights.com"
    assert "https://cloudflareinsights.com" in directives["connect-src"].split()
    assert directives["default-src"] == "'self'" and directives["style-src"] == "'self'"
    assert directives["frame-src"] == "'none'" and directives["object-src"] == "'none'"
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp


def test_no_inline_handlers_or_styles_were_added_to_the_site():
    for page in ("index", "terms", "privacy"):
        assert not re.search(r"\son[a-z]+=", TEXT[page]) and "style=" not in TEXT[page], page


# --- the metric -----------------------------------------------------------------------------------------------------------

def test_support_chat_rate_counts_troubled_users_who_reached_out_and_where():
    rows = [row("error_displayed", user="a", source="web", surface="report"), row("paywall_shown", user="b"),
            row("error_displayed", user="c", source="web", surface="scan"),
            row("support_chat_clicked", user="a", source="web", placement="report_error"),
            row("support_chat_clicked", user="x", source="extension", placement="extension")]  # never troubled
    result = measure(rows, "support_chat_rate")
    assert (result["numerator"], result["denominator"]) == (1, 3) and result["value"] == pytest.approx(1 / 3)
    assert result["breakdown"]["clicks_by_placement"] == {"report_error": 1, "extension": 1}


def test_support_chat_rate_reports_no_data_when_nobody_was_troubled():
    assert measure([], "support_chat_rate")["value"] is None


def test_decorative_section_backgrounds_cannot_widen_the_page_on_phones():
    rule = next(line for line in TEXT["css"].splitlines() if line.startswith(".hero, .how-section, .feature-section, .products-section {"))
    assert "overflow-x: clip" in rule, "background shapes past the screen edge made phones render the page wider than the screen"
