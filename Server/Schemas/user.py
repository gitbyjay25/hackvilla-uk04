"""
User schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserMeResponse(BaseModel):
    """Response model for /auth/me endpoint"""
    id: str
    email: str
    name: str
    full_name: Optional[str] = None
    role: str
    created_at: datetime
    picture: Optional[str] = None
    phone_number: Optional[str] = None
    linkedin_url: Optional[str] = None
    bio: Optional[str] = None
    
    class Config:
        from_attributes = True


class GoogleAuthRequestWithState(BaseModel):
    """Google OAuth authentication request with code"""
    code: str
    state: Optional[str] = None


class UserCreate(BaseModel):
    """User creation request"""
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class UserProfileUpdate(BaseModel):
    """Profile update request"""
    full_name: Optional[str] = None
    picture: Optional[str] = None
    phone_number: Optional[str] = None
    linkedin_url: Optional[str] = None
    bio: Optional[str] = None
