from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid


class WorkflowChange(BaseModel):
    type: str
    target: str
    description: str
    impact: str


class Workflow(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    proposed_changes: List[WorkflowChange] = []
    steps: List[Dict[str, Any]] = []  # Added for AI workflows
    pros: List[str] = []
    cons: List[str] = []
    complexity_score: int = 5  # 1-10
    complexity: str = "medium"  # low, medium, high
    risk_score: int = 5  # 1-10
    expected_impact: Dict[str, Any] = {}
    estimated_impact: float = 0.5  # 0-1
    tenant_id: Optional[str] = None
    
    def __init__(self, **data):
        if 'id' not in data or data['id'] is None:
            data['id'] = str(uuid.uuid4())
        super().__init__(**data)
