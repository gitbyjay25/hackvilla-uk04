"""Optional authentication dependency"""
from fastapi import Header, Depends
from typing import Optional
from core.auth import AuthContext, verify_api_key
from sqlalchemy.orm import Session
from db.base import get_db


async def optional_auth(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Optional[AuthContext]:
    """Optional authentication — returns None if no API key provided or key is invalid."""
    if not x_api_key:
        return None

    try:
        return verify_api_key(x_api_key, db)
    except Exception:
        return None
