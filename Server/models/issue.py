from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid


class Issue(BaseModel):
    id: Optional[str] = None
    severity: str  # low, medium, high, critical
    type: str
    description: str
    affected_nodes: List[str] = []
    affected_services: List[str] = []  # Added for consistency
    metric_value: Optional[float] = None
    evidence: Dict[str, Any] = {}
    recommendation: Optional[str] = None  # Added
    tenant_id: Optional[str] = None  # Added for multi-tenancy
    
    def __init__(self, **data):
        if 'id' not in data or data['id'] is None:
            data['id'] = str(uuid.uuid4())
        super().__init__(**data)
