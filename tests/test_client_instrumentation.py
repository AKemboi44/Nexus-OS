"""Website/extension telemetry stays consistent with the schema, the privacy gate and the CSP."""

import re
from pathlib import Path

import cloud_app
from app.analytics import schema

ROOT = Path(__file__).resolve().parent.parent
WEBSITE_JS = (ROOT / "website" / "app.js").read_text(encoding="utf-8")
WEBSITE_HTML = (ROOT / "website" / "index.html").read_text(encoding="utf-8")


def _sample_context(spec):
    sample = {}
    for key, prop in spec.props.items():
        if prop.kind == "str":
            sample[key] = prop.values[0] if prop.values else "sample"
        elif prop.kind in ("int", "float"):
            sample[key] = 1
        elif prop.kind == "bool":
            sample[key] = True
        else:
            sample[key] = "sample"
    return sample


def test_every_client_event_passes_the_privacy_gate_and_its_own_schema():
    client_specs = [s for s in schema.REGISTRY.values() if set(s.sources) & {schema.WEB, schema.EXTENSION}]
    assert client_specs
    for spec in client_specs:
        context = _sample_context(spec)
        gated = cloud_app.privacy_safe_analytics_context(context)  # raises if a string key is not allowed
        assert schema.validate(spec.name, gated, spec.sources[0]) == [], spec.name


def test_website_only_tracks_registered_web_events():
    tracked = set(re.findall(r"track\('([a-z_]+)'", WEBSITE_JS))
    assert {"workspace_opened", "results_viewed", "deliverable_clicked", "error_displayed"} <= tracked
    for name in tracked:
        spec = schema.get(name)
        assert spec is not None and schema.WEB in spec.sources, name


def test_website_never_sends_server_owned_outcome_events():
    for name in ("scan_started", "scan_completed", "report_started", "report_completed"):
        assert f"track('{name}'" not in WEBSITE_JS


def test_website_has_no_inline_styles_that_the_csp_would_block():
    headers = (ROOT / "website" / "_headers").read_text(encoding="utf-8")
    assert "style-src 'self'" in headers and "unsafe-inline" not in headers
    assert 'style="' not in WEBSITE_JS, "inline styles are ignored under style-src 'self'"
    assert "innerHTML = errorHtml" not in WEBSITE_JS


def test_report_error_card_uses_classes_and_text_nodes():
    assert "function showReportError(" in WEBSITE_JS
    assert "heading.textContent = title" in WEBSITE_JS and "code.textContent" in WEBSITE_JS
    css = (ROOT / "website" / "styles.css").read_text(encoding="utf-8")
    for selector in (".status-callout .status-title", ".status-callout .status-ref", ".status-callout.warning"):
        assert selector in css


def test_feedback_reasons_match_between_page_script_and_server():
    html_reasons = set(re.findall(r'id="reason_([a-z_]+)"', WEBSITE_HTML))
    js_reasons = set(re.findall(r"'([a-z_]+)'", re.search(r"FEEDBACK_REASON_IDS = \[(.*?)\]", WEBSITE_JS).group(1)))
    assert html_reasons == js_reasons == set(cloud_app.FEEDBACK_REASONS)
    for element in ("reportFeedback", "feedbackUp", "feedbackDown", "feedbackSend", "feedbackPrompt"):
        assert f'id="{element}"' in WEBSITE_HTML


def test_feedback_is_only_offered_when_the_server_returned_a_reference():
    assert "offerFeedback(reportResponse.reference, reportType)" in WEBSITE_JS
    assert "if (!panel || !reference) return hideFeedback();" in WEBSITE_JS
    assert "/v1/feedback" in WEBSITE_JS and "comment" not in WEBSITE_JS.split("submitFeedback")[1].split("wireFeedback")[0]


EXTENSION_JS = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")
EXTENSION_HTML = (ROOT / "extension" / "popup.html").read_text(encoding="utf-8")


def test_extension_feedback_matches_server_reasons_and_needs_a_reference():
    html_reasons = set(re.findall(r'id="reason_([a-z_]+)"', EXTENSION_HTML))
    js_reasons = set(re.findall(r"'([a-z_]+)'", re.search(r"FEEDBACK_REASON_IDS = \[(.*?)\]", EXTENSION_JS).group(1)))
    assert html_reasons == js_reasons == set(cloud_app.FEEDBACK_REASONS)
    for element in ("reportFeedback", "feedbackUp", "feedbackDown", "feedbackSend", "feedbackPrompt"):
        assert f'id="{element}"' in EXTENSION_HTML
    assert "offerFeedback(data.reference, activeReportType)" in EXTENSION_JS
    assert "if (!panel || !reference) return hideFeedback();" in EXTENSION_JS
    assert "/v1/feedback" in EXTENSION_JS


def test_extension_only_tracks_registered_extension_events():
    tracked = set(re.findall(r"sendAnalytics\('([a-z_]+)'", EXTENSION_JS))
    assert tracked, "extension should still send client-only events"
    for name in tracked:
        spec = schema.get(name)
        assert spec is not None and schema.EXTENSION in spec.sources, name
