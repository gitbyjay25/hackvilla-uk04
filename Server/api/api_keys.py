"""
API Key Management for Users
Allows logged-in users to manage their API keys for SDK authentication
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.base import get_db
from db.models import APIKey, User
from dependencies.auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import secrets
from datetime import datetime

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


def _normalize_key_preview(key_preview: str) -> str:
    """Return the stable key prefix used for revocation lookups."""
    return key_preview.split("...", 1)[0].strip()


class APIKeyCreate(BaseModel):
    name: str


class APIKeyResponse(BaseModel):
    key: str
    name: str
    created_at: str
    last_used: Optional[str]
    is_active: bool


class APIKeyListResponse(BaseModel):
    key_preview: str  # First 8 chars + last 4 chars
    name: str
    created_at: str
    last_used: Optional[str]
    is_active: bool


@router.post("/", response_model=APIKeyResponse)
async def create_api_key(
    data: APIKeyCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new API key for the authenticated user's tenant
    The key will be shown only once - save it securely!
    """
    # Get user from database to access tenant_id
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user or not user.tenant_id:
        raise HTTPException(status_code=400, detail="User has no tenant assigned")
    
    # Generate API key
    api_key = f"nex_{secrets.token_urlsafe(32)}"
    
    # Create API key object
    api_key_obj = APIKey(
        key=api_key,
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=data.name,
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(api_key_obj)
    db.commit()
    db.refresh(api_key_obj)
    
    return APIKeyResponse(
        key=api_key,
        name=api_key_obj.name,
        created_at=api_key_obj.created_at.isoformat(),
        last_used=api_key_obj.last_used.isoformat() if api_key_obj.last_used else None,
        is_active=api_key_obj.is_active
    )


@router.get("/", response_model=List[APIKeyListResponse])
async def list_api_keys(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all API keys for the authenticated user
    Keys are masked for security
    """
    # Get user from database to access tenant_id
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user or not user.tenant_id:
        raise HTTPException(status_code=400, detail="User has no tenant assigned")
    
    # Get all API keys for user's tenant
    api_keys = db.query(APIKey).filter(
        APIKey.tenant_id == user.tenant_id
    ).order_by(APIKey.created_at.desc()).all()
    
    return [
        APIKeyListResponse(
            key_preview=f"{key.key[:8]}...{key.key[-4:]}",
            name=key.name,
            created_at=key.created_at.isoformat(),
            last_used=key.last_used.isoformat() if key.last_used else None,
            is_active=key.is_active
        )
        for key in api_keys
    ]


@router.delete("/{key_preview}")
async def revoke_api_key(
    key_preview: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke (deactivate) an API key
    Use the first 8 characters of the key as key_preview
    """
    # Get user from database to access tenant_id
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user or not user.tenant_id:
        raise HTTPException(status_code=400, detail="User has no tenant assigned")
    
    normalized_preview = _normalize_key_preview(key_preview)

    # Find API key by prefix and tenant
    api_keys = db.query(APIKey).filter(
        APIKey.tenant_id == user.tenant_id
    ).all()
    
    matching_key = None
    for key in api_keys:
        if key.key.startswith(normalized_preview):
            matching_key = key
            break
    
    if not matching_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Deactivate the key
    matching_key.is_active = False
    db.commit()
    
    return {
        "message": "API key revoked successfully",
        "key_preview": f"{matching_key.key[:8]}...{matching_key.key[-4:]}"
    }
