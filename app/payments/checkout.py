"""Pack checkout: create an order, capture and verify it, and reconcile PayPal webhooks.

Every grant of access goes through `_settle`, which checks the amount, currency and buyer against
what the server recorded when it created the order, and credits exactly once.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from app.payments.catalog import Pack, get_pack, money

logger = logging.getLogger(__name__)


class CheckoutError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code, self.code, self.message = status_code, code, message
        super().__init__(message)


@dataclass
class CheckoutResult:
    status: str  # credited | already_credited | pending | ignored | refunded | failed
    order: Optional[Dict[str, Any]] = None
    pack: Optional[Pack] = None
    credited_now: bool = False
    detail: Dict[str, Any] = field(default_factory=dict)


def create_pack_checkout(paypal, store, user_id: str, pack_id: Optional[str]) -> Dict[str, Any]:
    pack = get_pack(pack_id)
    if pack is None:
        raise CheckoutError(400, "unknown_pack", "That pack is not available.")
    order = paypal.create_pack_order(pack, user_id, f"NX-{uuid.uuid4().hex[:24]}")
    approve_url = paypal.approval_url(order)
    store.create_order(order["id"], user_id, pack)
    return {"order_id": order["id"], "approve_url": approve_url, "pack": pack.public()}


def _capture_of(order_json: Dict[str, Any]) -> Dict[str, Any]:
    units = order_json.get("purchase_units") or [{}]
    captures = (units[0].get("payments") or {}).get("captures") or [{}]
    capture = dict(captures[0])
    capture.setdefault("custom_id", units[0].get("custom_id"))
    return capture


def _settle(store, order: Dict[str, Any], capture: Dict[str, Any], order_status: Optional[str] = "COMPLETED") -> CheckoutResult:
    """Verify a captured payment against the recorded order, then credit it once."""
    pack = get_pack(order["pack_id"])
    if pack is None:
        raise CheckoutError(500, "unknown_pack", "The purchased pack is no longer in the catalog.")
    if order["status"] == "credited":
        return CheckoutResult("already_credited", order, pack)
    if order["status"] in ("refunded", "failed"):
        raise CheckoutError(409, "order_closed", "This order can no longer be used.")

    capture_status = capture.get("status")
    if capture_status == "PENDING":
        store.mark_order(order["order_id"], "pending", "captured", capture.get("id"))
        return CheckoutResult("pending", order, pack)
    if order_status != "COMPLETED" or capture_status != "COMPLETED":
        raise CheckoutError(402, "payment_incomplete", "PayPal has not completed this payment.")

    amount = capture.get("amount") or {}
    try:
        paid = money(amount.get("value"))
    except Exception:
        paid = None
    if paid != order["amount"] or amount.get("currency_code") != order["currency"]:
        logger.error("Payment mismatch for order %s: paid %s %s, expected %s %s",
                     order["order_id"], amount.get("value"), amount.get("currency_code"),
                     order["amount"], order["currency"])
        raise CheckoutError(409, "payment_mismatch", "The payment does not match the order.")
    if capture.get("custom_id") and str(capture["custom_id"]) != order["user_id"]:
        logger.error("Buyer mismatch for order %s", order["order_id"])
        raise CheckoutError(409, "payment_mismatch", "The payment does not match the order.")

    credit = store.credit_pack_order(order, pack, capture.get("id"))
    if credit.get("credited"):
        return CheckoutResult("credited", order, pack, True, credit)
    return CheckoutResult("already_credited", order, pack, False, credit)


def capture_pack_order(paypal, store, user_id: str, order_id: str) -> CheckoutResult:
    order = store.get_order(order_id)
    if order is None or order["user_id"] != user_id:
        raise CheckoutError(404, "order_not_found", "Order not found.")
    if order["status"] == "credited":
        return CheckoutResult("already_credited", order, get_pack(order["pack_id"]))
    result = paypal.capture_order(order_id)
    return _settle(store, order, _capture_of(result), result.get("status"))


def _related_order_id(resource: Dict[str, Any]) -> Optional[str]:
    return ((resource.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")


def _capture_id_of_refund(resource: Dict[str, Any]) -> Optional[str]:
    related = ((resource.get("supplementary_data") or {}).get("related_ids") or {}).get("capture_id")
    if related:
        return related
    for link in resource.get("links") or []:
        if link.get("rel") == "up" and link.get("href"):
            return urlparse(link["href"]).path.rstrip("/").split("/")[-1]
    return None


def handle_paypal_event(paypal, store, event: Dict[str, Any]) -> CheckoutResult:
    """Reconcile one verified PayPal webhook event. Unknown events are ignored, never guessed at."""
    event_type = event.get("event_type") or ""
    resource = event.get("resource") or {}

    if event_type == "CHECKOUT.ORDER.APPROVED":
        order = store.get_order(resource.get("id") or "")
        if order is None:
            return CheckoutResult("ignored")
        if order["status"] == "credited":
            return CheckoutResult("already_credited", order, get_pack(order["pack_id"]))
        result = paypal.capture_order(order["order_id"])
        return _settle(store, order, _capture_of(result), result.get("status"))

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        order_id = _related_order_id(resource)
        order = store.get_order(order_id) if order_id else store.get_order_by_capture(resource.get("id") or "")
        if order is None:
            return CheckoutResult("ignored")
        return _settle(store, order, resource, "COMPLETED")

    if event_type == "PAYMENT.CAPTURE.DENIED":
        order_id = _related_order_id(resource)
        order = store.get_order(order_id) if order_id else None
        if order and store.mark_order(order["order_id"], "pending", "failed"):
            return CheckoutResult("failed", order)
        return CheckoutResult("ignored", order)

    if event_type in ("PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED"):
        reversed_ = event_type.endswith("REVERSED")
        capture_id = resource.get("id") if reversed_ else _capture_id_of_refund(resource)
        order = store.get_order_by_capture(capture_id) if capture_id else None
        if order is None:
            return CheckoutResult("ignored")
        refunded = money((resource.get("amount") or {}).get("value") or 0)
        if not reversed_ and refunded < order["amount"]:
            return CheckoutResult("ignored", order, detail={"reason": "partial_refund"})
        pack = get_pack(order["pack_id"])
        outcome = store.refund_pack_order(order["order_id"], pack)
        return CheckoutResult("refunded" if outcome.get("refunded") else "ignored", order, pack, detail=outcome)

    logger.info("Ignoring PayPal event type %s", event_type)
    return CheckoutResult("ignored")
