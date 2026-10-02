import os
from dataclasses import dataclass, field
from typing import Any, Dict, Set


@dataclass
class PricingConfig:
    """Configurable values for Nexus pricing, allowances, and A/B testing."""
    # Feature flag to enable/disable the new pricing model and paywall
    pricing_model_enabled: bool = True

    # Whitelisted emails with unlimited query and full access privileges
    whitelisted_emails: Set[str] = field(default_factory=lambda: {"akiptoo20@gmail.com"})

    # Free tier query allowance (queries per user per month)
    free_query_allowance: int = 1
    free_candidate_cap: int = 20

    # Paid Review Bundle configuration
    bundle_id: str = "review_bundle_standard"
    bundle_name: str = "Literature Review Bundle"
    bundle_query_allowance: int = 10
    bundle_price_usd: float = 29.00
    bundle_price_formatted: str = "29.00"
    bundle_description: str = (
        "Complete literature review bundle including comprehensive queries, "
        "synthesized Word report, Excel audit trail, query history, and priority synthesis."
    )

    # Paywall copy options
    paywall_headline: str = "Unlock Your Complete Literature Review Bundle"
    paywall_copy_variant: str = "review_bundle_v1"
    paywall_description: str = (
        "You've used your free discovery query for this month. "
        "Get the full Literature Review Bundle with 10 deep queries, full synthesis reports, "
        "complete audit trails, and priority queue processing."
    )

    @classmethod
    def from_env(cls) -> "PricingConfig":
        enabled_val = os.getenv("NEXUS_PRICING_MODEL_ENABLED", "true").lower() in ("true", "1", "yes")
        free_queries = int(os.getenv("NEXUS_FREE_QUERY_ALLOWANCE", "1"))
        free_cap = int(os.getenv("NEXUS_FREE_CANDIDATE_CAP", "20"))
        bundle_queries = int(os.getenv("NEXUS_BUNDLE_QUERY_ALLOWANCE", "10"))
        bundle_price = float(os.getenv("NEXUS_BUNDLE_PRICE_USD", "29.00"))
        bundle_id = os.getenv("NEXUS_BUNDLE_ID", "review_bundle_standard")
        whitelist_env = os.getenv("NEXUS_WHITELISTED_EMAILS", "akiptoo20@gmail.com")
        whitelisted = {email.strip().lower() for email in whitelist_env.split(",") if email.strip()}

        return cls(
            pricing_model_enabled=enabled_val,
            whitelisted_emails=whitelisted,
            free_query_allowance=free_queries,
            free_candidate_cap=free_cap,
            bundle_id=bundle_id,
            bundle_query_allowance=bundle_queries,
            bundle_price_usd=bundle_price,
            bundle_price_formatted=f"{bundle_price:.2f}",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pricing_model_enabled": self.pricing_model_enabled,
            "free_query_allowance": self.free_query_allowance,
            "free_candidate_cap": self.free_candidate_cap,
            "bundle_id": self.bundle_id,
            "bundle_name": self.bundle_name,
            "bundle_query_allowance": self.bundle_query_allowance,
            "bundle_price_usd": self.bundle_price_usd,
            "bundle_price_formatted": self.bundle_price_formatted,
            "bundle_description": self.bundle_description,
            "paywall_headline": self.paywall_headline,
            "paywall_copy_variant": self.paywall_copy_variant,
            "paywall_description": self.paywall_description,
        }


default_pricing_config = PricingConfig.from_env()
