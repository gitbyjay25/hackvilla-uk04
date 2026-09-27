"""Base exporter interface"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class Exporter(ABC):
    """Base exporter"""
    
    @abstractmethod
    def export(self, data: Dict[str, Any]):
        """Export data"""
        pass
    
    @abstractmethod
    def close(self):
        """Close exporter"""
        pass
