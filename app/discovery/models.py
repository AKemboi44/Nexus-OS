"""
Discovery models.

All discovery providers must return
DiscoveryResult objects.
"""

from pydantic import BaseModel

from models.source import Source

class DiscoveryResult(BaseModel):
     query : str
     provider: str
     sources : list[Source]