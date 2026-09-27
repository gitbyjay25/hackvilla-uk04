"""
Token schemas for authentication responses
"""
from pydantic import BaseModel
from typing import Optional


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str


class TokenResponse(BaseModel):
    """Authentication token response with user info"""
    access_token: str
    token_type: str
    user: dict


class GoogleAuthUrlResponse(BaseModel):
    """Google OAuth authorization URL response"""
    auth_url: str


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True
