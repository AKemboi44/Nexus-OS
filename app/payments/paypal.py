import base64
import os
from typing import Any, Dict

import requests


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

    def _require_credentials(self):
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
        response.raise_for_status()
        return response.json()

    def create_order(self, plan: str, user_id: str) -> Dict[str, Any]:
        plans = {
            "pro": ("19.00", "Research Pro"),
            "ultimate": ("49.00", "Research Ultimate"),
        }
        amount, description = plans.get(plan, plans["pro"])
        return self._request(
            "POST",
            "/v2/checkout/orders",
            json={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": f"nexus-{plan}",
                        "description": description,
                        "custom_id": str(user_id)[:127],
                        "amount": {"currency_code": "USD", "value": amount},
                    }
                ],
                "application_context": {
                    "brand_name": "Nexus Research AI",
                    "user_action": "PAY_NOW",
                    "return_url": os.getenv("PAYPAL_RETURN_URL", ""),
                    "cancel_url": os.getenv("PAYPAL_CANCEL_URL", ""),
                },
            },
        )

    def create_subscription(self, plan: str, user_id: str) -> Dict[str, Any]:
        plan_ids = {
            "pro": os.getenv("PAYPAL_PLAN_ID_PRO"),
            "ultimate": os.getenv("PAYPAL_PLAN_ID_ULTIMATE"),
        }
        plan_id = plan_ids.get(plan, plan_ids["pro"])
        if not plan_id:
            raise RuntimeError(f"PayPal subscription plan ID is not configured for: {plan}.")
        return self._request(
            "POST",
            "/v1/billing/subscriptions",
            json={
                "plan_id": plan_id,
                "custom_id": str(user_id)[:127],
                "application_context": {
                    "brand_name": "Nexus Research AI",
                    "user_action": "SUBSCRIBE_NOW",
                    "return_url": os.getenv("PAYPAL_RETURN_URL", ""),
                    "cancel_url": os.getenv("PAYPAL_CANCEL_URL", ""),
                },
            },
        )

    def capture_order(self, order_id: str) -> Dict[str, Any]:
        if not order_id or len(order_id) > 100:
            raise ValueError("A valid PayPal order ID is required.")
        return self._request("POST", f"/v2/checkout/orders/{order_id}/capture", json={})

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
