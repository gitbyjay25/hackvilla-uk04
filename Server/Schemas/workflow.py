from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional


class SchemaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")


class WorkflowChange(SchemaModel):
    type: str
    target: str
    description: str
    impact: str = ""


class Workflow(SchemaModel):
    id: Optional[str] = None
    name: str
    description: str
    proposed_changes: List[WorkflowChange] = Field(default_factory=list)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    complexity_score: int = 5  # 1-10
    complexity: str = "medium"  # low, medium, high
    risk_score: int = 5  # 1-10
    expected_impact: Dict[str, Any] = Field(default_factory=dict)
    estimated_impact: float = 0.5  # 0-1
    tenant_id: Optional[str] = None


class WorkflowsResponse(SchemaModel):
    workflows: List[Workflow]
    generated_at: str


class WorkflowComparison(SchemaModel):
    workflows: List[Workflow]
    recommendation: Any
    comparison_matrix: Dict[str, Any]
