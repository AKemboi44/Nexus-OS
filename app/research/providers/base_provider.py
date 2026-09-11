from abc import ABC, abstractmethod
from typing import Dict, Any, List

class DiscoveryProvider(ABC):
    """
    Contract interface for all Nexus Research domain collection engines.
    Ensures plug-and-play extensibility across different industry datasets.
    """
    @abstractmethod
    def fetch_raw_sources(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Queries the underlying domain endpoint database."""
        pass

    @abstractmethod
    def normalize_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Maps varying source attributes into the canonical Nexus schema frame."""
        pass