from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional


class Span(BaseModel):
    trace_id: str = Field(..., min_length=1, max_length=64)
    span_id: str = Field(..., min_length=1, max_length=64)
    parent_span_id: Optional[str] = Field(None, max_length=64)
    service_name: str = Field(..., min_length=1, max_length=255)
    operation: str = Field(..., min_length=1, max_length=255)
    kind: str = Field(..., pattern="^(server|client)$")
    start_time: datetime
    end_time: datetime
    latency_ms: float = Field(..., ge=0)
    status_code: Optional[int] = Field(None, ge=0, le=599)
    error: Optional[str] = None
    downstream: Optional[str] = Field(None, max_length=255)
    
    @field_validator('end_time')
    @classmethod
    def validate_end_after_start(cls, v, info):
        if 'start_time' in info.data and v < info.data['start_time']:
            raise ValueError('end_time must be after start_time')
        return v
