"""What the server sells. Clients send only a pack id; price, scans and validity come from here."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

from app.payments.config import PricingConfig, default_pricing_config

CENTS = Decimal("0.01")


@dataclass(frozen=True)
class Pack:
    id: str
    name: str
    price: Decimal
    currency: str
    scans: int
    validity_days: int
    description: str

    @property
    def price_text(self) -> str:
        return f"{self.price:.2f}"

    def public(self) -> Dict[str, object]:
        return {
            "id": self.id, "name": self.name, "price": self.price_text, "currency": self.currency,
            "scans": self.scans, "validity_days": self.validity_days, "description": self.description,
        }


def money(value) -> Decimal:
    """Normalise a PayPal or database amount ("29.00", 29, 29.0) to two decimal places."""
    return Decimal(str(value)).quantize(CENTS)


def build_catalog(config: Optional[PricingConfig] = None) -> Dict[str, Pack]:
    cfg = config or default_pricing_config
    pack = Pack(
        id=cfg.bundle_id,
        name=cfg.bundle_name,
        price=money(cfg.bundle_price_usd),
        currency=cfg.pack_currency,
        scans=cfg.bundle_query_allowance,
        validity_days=cfg.pack_validity_days,
        description=cfg.bundle_description,
    )
    return {pack.id: pack}


def default_pack(config: Optional[PricingConfig] = None) -> Pack:
    return next(iter(build_catalog(config).values()))


def get_pack(pack_id: Optional[str], config: Optional[PricingConfig] = None) -> Optional[Pack]:
    """The requested pack, or the default when none is named. None for an unknown id."""
    catalog = build_catalog(config)
    if not pack_id:
        return default_pack(config)
    return catalog.get(pack_id)
