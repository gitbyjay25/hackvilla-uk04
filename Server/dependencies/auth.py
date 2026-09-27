"""
Authentication dependencies for FastAPI routes
"""
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
from core.security import verify_token
from crud.user import get_user_by_id
from db.base import get_db
from sqlalchemy.orm import Session
from datetime import datetime

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token
    
    Args:
        credentials: HTTP Bearer token credentials
        db: Database session
        
    Returns:
        User information dictionary
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Verify token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user ID from token
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    user = get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "auth_provider": user.auth_provider,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current active user (must be active)
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        Active user information dictionary
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return current_user


def get_tenant_id_from_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    """
    Get tenant_id from JWT token for dashboard access
    
    Args:
        credentials: HTTP Bearer token credentials
        db: Database session
        
    Returns:
        tenant_id string
        
    Raises:
        HTTPException: If token is invalid or user has no tenant
    """
    token = credentials.credentials
    
    # Verify token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user ID from token
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    from db.models import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant assigned"
        )
    
    return user.tenant_id


def get_tenant_id_from_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> str:
    """
    Get tenant_id from X-API-Key header for SDK authentication
    
    Args:
        x_api_key: API key from X-API-Key header
        db: Database session
        
    Returns:
        tenant_id string
        
    Raises:
        HTTPException: If API key is invalid or inactive
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required. Provide it in X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Get API key from database
    from db.models import APIKey
    api_key = db.query(APIKey).filter(APIKey.key == x_api_key).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has been revoked",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Update last_used timestamp
    api_key.last_used = datetime.utcnow()
    db.commit()
    
    return api_key.tenant_id


def get_tenant_id_from_jwt_or_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> str:
    """
    Get tenant_id from either JWT token or API key
    This allows both dashboard (JWT) and SDK (API key) to access the same endpoints
    
    Args:
        x_api_key: Optional API key from X-API-Key header
        credentials: Optional HTTP Bearer token credentials
        db: Database session
        
    Returns:
        tenant_id string
        
    Raises:
        HTTPException: If neither authentication method is valid
    """
    # Try API key first
    if x_api_key:
        try:
            return get_tenant_id_from_api_key(x_api_key, db)
        except HTTPException:
            pass
    
    # Try JWT token
    if credentials:
        try:
            return get_tenant_id_from_jwt(credentials, db)
        except HTTPException:
            pass
    
    # Neither worked
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide either Bearer token or X-API-Key header",
        headers={"WWW-Authenticate": "Bearer"},
    )

