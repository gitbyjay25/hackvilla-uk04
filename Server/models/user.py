"""User and tenant models"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class User(BaseModel):
    """User model"""
    id: str
    email: EmailStr
    tenant_id: str
    api_key: str
    created_at: datetime
    is_active: bool = True
    
    class Config:
        from_attributes = True


class Tenant(BaseModel):
    """Tenant/Organization model"""
    id: str
    name: str
    created_at: datetime
    is_active: bool = True
    max_spans_per_day: int = 1000000  # Rate limit
    
    class Config:
        from_attributes = True


class APIKey(BaseModel):
    """API Key model"""
    key: str
    tenant_id: str
    user_id: Optional[str]
    name: str
    is_active: bool = True
    created_at: datetime
    last_used: Optional[datetime]
    
    class Config:
        from_attributes = True
