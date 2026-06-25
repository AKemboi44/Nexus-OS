"""
Nexus OS v0.5.0 - Agent Layer
Generated for clarity and high maintainability.
"""
import os
import sys

# Path resolution to project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    def announce(self, message: str):
        print(f"[{self.name} | {self.role}]: {message}")

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        pass
