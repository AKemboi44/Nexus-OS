import hashlib
import random
from typing import Optional


class ExperimentService:
    """Assigns and resolves consistent A/B test variants for users and queries."""

    VARIANT_A = "variant_a"  # Full candidate set with included & excluded visible, exclusion reasons front and centre
    VARIANT_B = "variant_b"  # Included set visible, excluded behind "show what we filtered out" reveal

    @classmethod
    def get_variant_for_user(cls, user_id: Optional[str]) -> str:
        """
        Deterministically assign a user to Variant A or Variant B based on user_id hash.
        If user_id is missing or anonymous, returns random variant or default.
        """
        if not user_id or user_id in ("anonymous", "unknown"):
            return cls.VARIANT_A
        # Stable deterministic hashing modulo 2
        digest = hashlib.sha256(str(user_id).strip().lower().encode("utf-8")).hexdigest()
        hash_val = int(digest[:8], 16)
        return cls.VARIANT_A if (hash_val % 2 == 0) else cls.VARIANT_B
