from abc import ABC, abstractmethod
from typing import Dict, Any, List

class DiscoveryProvider(ABC):
    """
    Contract interface for all Nexus Research domain collection engines.
    Ensures plug-and-play extensibility across different industry datasets.
    """
    @abstractmethod
    def fetch_raw_sources(self, query: str, limit: int = 5, hints: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Queries the underlying domain endpoint database.

        `hints` (optional) are things the selected criteria let the provider filter on at search time:
        year_from, open_access, min_citations, review, work_types.
        """
        pass

    def supports_hints(self, hints: Dict[str, Any]) -> bool:
        """Whether a targeted search with these hints would be different from, and better than, the normal one."""
        return False

    @abstractmethod
    def normalize_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Maps varying source attributes into the canonical Nexus schema frame."""
        pass