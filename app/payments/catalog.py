"""What the server sells. Clients send only a pack id; price, scans and validity come from here."""

import json
import logging
import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from app.payments.config import PricingConfig, default_pricing_config

logger = logging.getLogger(__name__)

CENTS = Decimal("0.01")
_PACK_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
MAX_PACKS = 6


@dataclass(frozen=True)
class Pack:
    id: str
    name: str
    price: Decimal
    currency: str
    scans: int
    validity_days: int
    description: str
    badge: str = ""

    @property
    def price_text(self) -> str:
        return f"{self.price:.2f}"

    @property
    def per_scan_text(self) -> str:
        return f"{(self.price / self.scans).quantize(CENTS):.2f}"

    def public(self) -> Dict[str, object]:
        return {
            "id": self.id, "name": self.name, "price": self.price_text, "currency": self.currency,
            "scans": self.scans, "validity_days": self.validity_days, "description": self.description,
            "badge": self.badge, "per_scan": self.per_scan_text,
        }


def money(value) -> Decimal:
    """Normalise a PayPal or database amount ("10.00", 10, 10.0) to two decimal places."""
    return Decimal(str(value)).quantize(CENTS)


def _default_packs(cfg: PricingConfig) -> List[Pack]:
    starter = Pack(
        id=cfg.bundle_id, name=cfg.bundle_name, price=money(cfg.bundle_price_usd),
        currency=cfg.pack_currency, scans=cfg.bundle_query_allowance,
        validity_days=cfg.pack_validity_days, description=cfg.bundle_description,
        badge="Most students start here",
    )
    researcher = Pack(
        id="researcher_50", name="Researcher Pack",
        price=money(os.getenv("NEXUS_RESEARCHER_PRICE_USD", "19.00")), currency=cfg.pack_currency,
        scans=int(os.getenv("NEXUS_RESEARCHER_SCANS", "50")), validity_days=cfg.pack_validity_days,
        description="Researcher Pack: 50 scans with the full Excel audit trail and Word reports.",
        badge="Best value",
    )
    return [starter, researcher]


def _packs_from_json(raw: str, cfg: PricingConfig) -> Optional[List[Pack]]:
    """A complete replacement catalog from NEXUS_PACKS_JSON, or None if any entry is invalid."""
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_PACKS:
            raise ValueError("expected a list of 1 to %d packs" % MAX_PACKS)
        packs, seen = [], set()
        for entry in entries:
            pack_id = str(entry["id"])
            price, scans = money(entry["price"]), int(entry["scans"])
            if not _PACK_ID.match(pack_id) or pack_id in seen or price <= 0 or scans < 1:
                raise ValueError(f"invalid pack {pack_id!r}")
            seen.add(pack_id)
            packs.append(Pack(
                id=pack_id, name=str(entry["name"])[:60], price=price, currency=cfg.pack_currency,
                scans=scans, validity_days=int(entry.get("validity_days", cfg.pack_validity_days)),
                description=str(entry.get("description", ""))[:240], badge=str(entry.get("badge", ""))[:40],
            ))
        return packs
    except (ValueError, KeyError, TypeError, InvalidOperation) as error:
        logger.error("NEXUS_PACKS_JSON ignored, using the default packs: %s", error)
        return None


def build_catalog(config: Optional[PricingConfig] = None) -> Dict[str, Pack]:
    """The packs on sale, in display order. The first is the default."""
    cfg = config or default_pricing_config
    raw = os.getenv("NEXUS_PACKS_JSON")
    packs = (_packs_from_json(raw, cfg) if raw else None) or _default_packs(cfg)
    return {pack.id: pack for pack in packs}


def all_packs(config: Optional[PricingConfig] = None) -> List[Pack]:
    return list(build_catalog(config).values())


def default_pack(config: Optional[PricingConfig] = None) -> Pack:
    return next(iter(build_catalog(config).values()))


def get_pack(pack_id: Optional[str], config: Optional[PricingConfig] = None) -> Optional[Pack]:
    """The requested pack, or the default when none is named. None for an unknown id."""
    if not pack_id:
        return default_pack(config)
    return build_catalog(config).get(pack_id)
