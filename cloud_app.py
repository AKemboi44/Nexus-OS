# cloud_app.py - Block 1 of 2
import os
import sys
import secrets
import requests
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.research.research_pipeline import ResearchPipeline
from app.analytics.event_store import AnalyticsEventStore
from app.payments.paypal import PayPalClient
from app.payments.entitlements import EntitlementStore

app = FastAPI(title="Nexus Research AI Gateway", version="1.0.0")
allowed_origins = os.getenv("NEXUS_ALLOWED_ORIGINS", os.getenv("CORS_origins", "*"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
pipeline = ResearchPipeline()
analytics = AnalyticsEventStore()
paypal = PayPalClient()
entitlements = EntitlementStore()

class ScanRequest(BaseModel):
    topic: str
    max_sources: Optional[int] = 5
    domain: Optional[str] = "scholarly"

class AnalyticsEvent(BaseModel):
    user_id: Optional[str] = "anonymous"
    session_id: Optional[str] = "unknown"
    event: str
    timestamp: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class PayPalOrderRequest(BaseModel):
    plan: str = "pro"
    user_id: str = "anonymous"


class PayPalCaptureRequest(BaseModel):
    order_id: str
    user_id: str = "anonymous"


def require_admin(x_admin_token: Optional[str]):
    configured = os.getenv("NEXUS_ADMIN_TOKEN")
    if not configured or not x_admin_token or not secrets.compare_digest(x_admin_token, configured):
        raise HTTPException(status_code=401, detail="Admin authentication required.")


def require_api_access(x_api_key: Optional[str]):
    configured = os.getenv("NEXUS_API_KEY")
    if configured and x_api_key != configured:
        raise HTTPException(status_code=401, detail="API authentication required.")


def require_supabase_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="A valid Supabase access token is required.")

    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise HTTPException(status_code=503, detail="Supabase authentication is not configured.")

    try:
        response = requests.get(
            f"{supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": service_role_key,
                "Authorization": authorization,
            },
            timeout=5,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=503, detail="Supabase authentication service is unavailable.") from error

    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Supabase access token is invalid or expired.")
    if not response.ok:
        raise HTTPException(status_code=503, detail="Could not validate the Supabase access token.")

    try:
        user = response.json()
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Supabase returned an invalid authentication response.") from error
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(status_code=401, detail="Supabase access token did not identify a user.")
    return user


def supabase_user_id(user: Dict[str, Any]) -> str:
    return str(user.get("email") or user["id"])

# cloud_app.py - Block 2 of 2
@app.post("/v1/scan")
async def execute_cloud_scan(
    payload: ScanRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    require_supabase_user(authorization)
    require_api_access(x_api_key)
    if not payload.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be blank.")
    try:
        result_data = pipeline.run_research(
            query=payload.topic,
            max_sources=payload.max_sources
        )
        if hasattr(result_data, "to_dict"):
            return result_data.to_dict()
        if hasattr(result_data, "model_dump"):
            return result_data.model_dump()
        return result_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/analytics")
async def log_telemetry_event(
    event: AnalyticsEvent,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    try:
        analytics.record(
            event_name=event.event,
            user_id=supabase_user_id(user),
            session_id=event.session_id or "unknown",
            properties=event.context,
            occurred_at=event.timestamp,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"status": "logged"}


@app.get("/v1/admin/analytics")
async def get_admin_analytics(days: int = 30, x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    return analytics.summary(days=days)


@app.post("/v1/paypal/orders")
async def create_paypal_order(
    payload: PayPalOrderRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    user_id = supabase_user_id(user)
    try:
        order = paypal.create_order(payload.plan, user_id)
        analytics.record(
            "checkout_started",
            user_id,
            properties={"provider": "paypal", "plan": payload.plan, "order_id": order.get("id")},
        )
        return order
    except (RuntimeError, ValueError) as error:
        analytics.record(
            "payment_failed",
            user_id,
            properties={"provider": "paypal", "error_code": "CONFIGURATION", "message": str(error)},
        )
        raise HTTPException(status_code=503, detail=str(error))
    except Exception as error:
        analytics.record(
            "payment_failed",
            user_id,
            properties={"provider": "paypal", "error_code": "PAYPAL_API_ERROR", "message": str(error)},
        )
        raise HTTPException(status_code=502, detail="PayPal order creation failed.")


@app.post("/v1/paypal/subscriptions")
async def create_paypal_subscription(
    payload: PayPalOrderRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    user_id = supabase_user_id(user)
    try:
        subscription = paypal.create_subscription(payload.plan, user_id)
        analytics.record(
            "checkout_started",
            user_id,
            properties={
                "provider": "paypal",
                "payment_type": "subscription",
                "plan": payload.plan,
                "subscription_id": subscription.get("id"),
            },
        )
        if subscription.get("id"):
            entitlements.upsert(
                user_id,
                "paypal",
                subscription["id"],
                "PENDING",
                plan=payload.plan,
            )
        return subscription
    except (RuntimeError, ValueError) as error:
        analytics.record(
            "payment_failed",
            user_id,
            properties={"provider": "paypal", "error_code": "CONFIGURATION", "message": str(error)},
        )
        raise HTTPException(status_code=503, detail=str(error))
    except Exception:
        analytics.record(
            "payment_failed",
            user_id,
            properties={"provider": "paypal", "error_code": "PAYPAL_API_ERROR"},
        )
        raise HTTPException(status_code=502, detail="PayPal subscription creation failed.")


@app.post("/v1/paypal/capture")
async def capture_paypal_order(
    payload: PayPalCaptureRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    user_id = supabase_user_id(user)
    try:
        result = paypal.capture_order(payload.order_id)
        status = result.get("status")
        event_name = "payment_completed" if status == "COMPLETED" else "payment_pending"
        if status == "COMPLETED":
            purchase_units = result.get("purchase_units") or []
            custom_id = (purchase_units[0] if purchase_units else {}).get("custom_id")
            if custom_id:
                entitlements.upsert(
                    custom_id,
                    "paypal",
                    payload.order_id,
                    "COMPLETED",
                    plan=(purchase_units[0].get("reference_id") if purchase_units else None),
                )
        analytics.record(
            event_name,
            user_id,
            properties={"provider": "paypal", "order_id": payload.order_id, "status": status},
        )
        return result
    except Exception:
        analytics.record(
            "payment_failed",
            user_id,
            properties={
                "provider": "paypal",
                "error_code": "CAPTURE_FAILED",
                "order_id": payload.order_id,
            },
        )
        raise HTTPException(status_code=502, detail="PayPal payment capture failed.")


@app.get("/v1/entitlements/{user_id}")
async def get_entitlement(
    user_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    if not user_id or len(user_id) > 200:
        raise HTTPException(status_code=400, detail="Invalid user ID.")
    allowed_ids = {str(user["id"])}
    if user.get("email"):
        allowed_ids.add(str(user["email"]))
    if user_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Cannot access another user's entitlements.")
    record = entitlements.get(user_id)
    return {
        "user_id": user_id,
        "active": entitlements.is_active(user_id),
        "entitlement": record,
    }


@app.post("/v1/paypal/webhook")
async def paypal_webhook(request: Request):
    event = await request.json()
    headers = {key.upper(): value for key, value in request.headers.items()}
    try:
        if not paypal.verify_webhook_signature(headers, event):
            raise HTTPException(status_code=400, detail="Invalid PayPal webhook signature.")
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))

    event_id = event.get("id")
    if not entitlements.claim_event(event_id):
        return {"status": "already_processed"}

    resource = event.get("resource", {})
    event_type = event.get("event_type", "")
    provider_id = resource.get("id") or resource.get("billing_agreement_id")
    user_id = resource.get("custom_id") or resource.get("subscriber", {}).get("payer_id")
    if not user_id and provider_id:
        prior = entitlements.get_by_provider("paypal", provider_id)
        user_id = prior.get("user_key") if prior else None
    if "ACTIVATED" in event_type or "PAYMENT.COMPLETED" in event_type:
        status = "ACTIVE"
    elif any(value in event_type for value in ("CANCEL", "SUSPEND", "EXPIRED", "REVOKED")):
        status = "CANCELLED"
    else:
        status = "PENDING"
    if provider_id and user_id:
        entitlements.upsert(
            user_id,
            "paypal",
            provider_id,
            status,
            plan=resource.get("plan_id"),
        )
    analytics.record(
        "paypal_webhook_received",
        user_id or "anonymous",
        properties={"event_type": event_type, "provider_id": provider_id, "status": status},
    )
    return {"status": "processed"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("cloud_app.py", host="0.0.0.0", port=8000, reload=True)
