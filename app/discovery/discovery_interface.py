
from abc import ABC, abstractmethod


# NexusOs Contract
class DiscoveryProvider(ABC):
     @abstractmethod
     def search(self, query: str):
         pass
