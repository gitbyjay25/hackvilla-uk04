"""Authentication and authorization middleware"""
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
from db.base import get_db
from db.models import APIKey, Tenant
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AuthContext:
    """Authentication context for current request"""
    def __init__(self, tenant_id: str, api_key: str, user_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.api_key = api_key
        self.user_id = user_id


async def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> AuthContext:
    """
    Verify API key and return auth context.
    This runs on every request.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    # Check cache first (in production, use Redis)
    # cached = _get_cached_api_key(x_api_key, str(db.bind.url))
    # if cached:
    #     return AuthContext(tenant_id=cached[0], api_key=x_api_key, user_id=cached[1])
    
    # Query database
    api_key_obj = db.query(APIKey).filter(
        APIKey.key == x_api_key,
        APIKey.is_active == True
    ).first()
    
    if not api_key_obj:
        logger.warning(f"Invalid API key attempted: {x_api_key[:8]}...")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Check tenant is active
    tenant = db.query(Tenant).filter(
        Tenant.id == api_key_obj.tenant_id,
        Tenant.is_active == True
    ).first()
    
    if not tenant:
        logger.warning(f"Inactive tenant attempted access: {api_key_obj.tenant_id}")
        raise HTTPException(status_code=403, detail="Tenant inactive")
    
    # Update last_used timestamp (don't block the request)
    try:
        api_key_obj.last_used = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to update API key last_used: {e}")
        pass  # Don't fail request if update fails
    
    logger.info(f"Authenticated request for tenant: {tenant.id}")
    
    return AuthContext(
        tenant_id=api_key_obj.tenant_id,
        api_key=x_api_key,
        user_id=api_key_obj.user_id
    )


def get_tenant_id(auth: AuthContext = Depends(verify_api_key)) -> str:
    """Convenience function to extract tenant_id"""
    return auth.tenant_id
