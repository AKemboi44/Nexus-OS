import base64
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from app.payments.catalog import Pack

_ORDER_ID = re.compile(r"^[A-Za-z0-9_-]{5,100}$")


class PayPalError(RuntimeError):
    """A PayPal API call that was rejected, with PayPal's own error name and issue codes."""

    def __init__(self, status_code: int, name: str = "", message: str = "", issues: Optional[List[str]] = None):
        self.status_code = status_code
        self.name = name
        self.issues = issues or []
        super().__init__(f"PayPal request failed ({status_code} {name}): {message}".strip())


class PayPalClient:
    """PayPal API adapter. Credentials stay server-side."""

    def __init__(self):
        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = os.getenv("PAYPAL_CLIENT_SECRET")
        self.mode = os.getenv("PAYPAL_MODE", "sandbox").lower()
        self.base_url = (
            "https://api-m.sandbox.paypal.com"
            if self.mode == "sandbox"
            else "https://api-m.paypal.com"
        )

    def is_configured(self) -> bool:
        return bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET"))

    def _require_credentials(self):
        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = os.getenv("PAYPAL_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise RuntimeError("PayPal credentials are not configured on the server.")

    def _access_token(self) -> str:
        self._require_credentials()
        encoded = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("ascii")
        response = requests.post(
            f"{self.base_url}/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {encoded}",
                "Accept": "application/json",
                "Accept-Language": "en_US",
            },
            data={"grant_type": "client_credentials"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        token = self._access_token()
        headers = kwargs.pop("headers", {})
        headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            timeout=30,
            **kwargs,
        )
        if not response.ok:
            try:
                body = response.json()
            except ValueError:
                body = {}
            raise PayPalError(
                response.status_code,
                str(body.get("name") or ""),
                str(body.get("message") or "")[:200],
                [str(d.get("issue")) for d in body.get("details", []) if isinstance(d, dict) and d.get("issue")],
            )
        return response.json() if response.content else {}

    def create_pack_order(self, pack: Pack, user_id: str, invoice_id: str) -> Dict[str, Any]:
        """Create an order whose amount comes from the server's catalog, never from the client."""
        return self._request(
            "POST",
            "/v2/checkout/orders",
            json={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": pack.id[:127],
                        "description": f"{pack.name} ({pack.scans} scans)"[:127],
                        "custom_id": str(user_id)[:127],
                        "invoice_id": invoice_id[:127],
                        "amount": {"currency_code": pack.currency, "value": pack.price_text},
                    }
                ],
                "application_context": {
                    "brand_name": "Nexus Research AI",
                    "user_action": "PAY_NOW",
                    "shipping_preference": "NO_SHIPPING",
                    "return_url": os.getenv("PAYPAL_RETURN_URL", ""),
                    "cancel_url": os.getenv("PAYPAL_CANCEL_URL", ""),
                },
            },
        )

    @staticmethod
    def approval_url(order: Dict[str, Any]) -> str:
        """The PayPal page the buyer approves on. Refuses anything that is not a paypal.com link."""
        for link in order.get("links", []):
            if link.get("rel") in ("payer-action", "approve") and link.get("href"):
                host = (urlparse(link["href"]).hostname or "").lower()
                if urlparse(link["href"]).scheme == "https" and (host == "paypal.com" or host.endswith(".paypal.com")):
                    return link["href"]
        raise PayPalError(502, "NO_APPROVAL_LINK", "PayPal did not return a valid approval link.")

    @staticmethod
    def _checked_order_id(order_id: str) -> str:
        if not order_id or not _ORDER_ID.match(order_id):
            raise ValueError("A valid PayPal order ID is required.")
        return order_id

    def get_order(self, order_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/v2/checkout/orders/{self._checked_order_id(order_id)}")

    def capture_order(self, order_id: str) -> Dict[str, Any]:
        """Capture an approved order. A repeat call returns the existing captured order."""
        order_id = self._checked_order_id(order_id)
        try:
            return self._request("POST", f"/v2/checkout/orders/{order_id}/capture", json={})
        except PayPalError as error:
            if "ORDER_ALREADY_CAPTURED" in error.issues:
                return self.get_order(order_id)
            raise

    def verify_webhook_signature(self, headers: Dict[str, str], webhook_event: Dict[str, Any]) -> bool:
        webhook_id = os.getenv("PAYPAL_WEBHOOK_ID")
        if not webhook_id:
            raise RuntimeError("PAYPAL_WEBHOOK_ID is not configured.")
        result = self._request(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            json={
                "auth_algo": headers.get("PAYPAL-AUTH-ALGO"),
                "cert_url": headers.get("PAYPAL-CERT-URL"),
                "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID"),
                "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG"),
                "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME"),
                "webhook_id": webhook_id,
                "webhook_event": webhook_event,
            },
        )
        return result.get("verification_status") == "SUCCESS"
