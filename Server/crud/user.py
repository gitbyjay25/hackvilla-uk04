"""
CRUD operations for User model
"""
from typing import Optional, Tuple
from db.models import User, Tenant
from db.base import get_db, SessionLocal
from datetime import datetime
from sqlalchemy.orm import Session
from core.security import get_password_hash
import uuid


def _get_session(db: Optional[Session]) -> Tuple[Session, bool]:
    """Return *(session, owned)* where *owned* means the caller must close it."""
    if db is not None:
        return db, False
    return SessionLocal(), True


def get_user_by_id(user_id: str, db: Session = None) -> Optional[User]:
    """
    Get user by ID
    
    Args:
        user_id: User ID string
        db: Database session
        
    Returns:
        User object or None if not found
    """
    _db, owned = _get_session(db)
    try:
        user = _db.query(User).filter(User.id == user_id).first()
        return user
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None
    finally:
        if owned:
            _db.close()


def get_user_by_email(email: str, db: Session = None) -> Optional[User]:
    """
    Get user by email
    
    Args:
        email: User email address
        db: Database session
        
    Returns:
        User object or None if not found
    """
    _db, owned = _get_session(db)
    try:
        user = _db.query(User).filter(User.email == email.lower()).first()
        return user
    except Exception as e:
        print(f"Error getting user by email: {e}")
        return None
    finally:
        if owned:
            _db.close()


def create_google_user(
    email: str,
    google_id: str,
    full_name: Optional[str] = None,
    picture: Optional[str] = None,
    db: Session = None,
) -> User:
    """
    Create or update Google OAuth user
    
    Args:
        email: User email from Google
        google_id: Google user ID
        full_name: User's full name
        picture: Profile picture URL
        db: Database session
        
    Returns:
        User object
    """
    if db is None:
        _db = SessionLocal()
        try:
            return _create_google_user_impl(email, google_id, full_name, picture, _db)
        finally:
            _db.close()
    return _create_google_user_impl(email, google_id, full_name, picture, db)


def _create_google_user_impl(
    email: str,
    google_id: str,
    full_name: Optional[str] = None,
    picture: Optional[str] = None,
    db: Session = None,
) -> User:
    # Check if user exists
    existing_user = get_user_by_email(email, db)

    if existing_user:
        # Update existing user with Google info
        existing_user.google_id = google_id
        existing_user.auth_provider = "google"
        existing_user.is_active = True
        existing_user.is_verified = True
        if full_name:
            existing_user.full_name = full_name
        if picture:
            existing_user.picture = picture
        existing_user.updated_at = datetime.utcnow()
        
        # Create tenant if missing
        if not existing_user.tenant_id:
            tenant_id = str(uuid.uuid4())
            tenant = Tenant(
                id=tenant_id,
                name=f"{full_name or email.split('@')[0]}'s Organization",
                is_active=True
            )
            db.add(tenant)
            existing_user.tenant_id = tenant_id
        
        db.commit()
        db.refresh(existing_user)
        return existing_user
    
    # Create tenant for new user
    tenant_id = str(uuid.uuid4())
    tenant = Tenant(
        id=tenant_id,
        name=f"{full_name or email.split('@')[0]}'s Organization",
        is_active=True
    )
    db.add(tenant)
    
    # Create new user
    new_user = User(
        id=str(uuid.uuid4()),
        email=email.lower(),
        google_id=google_id,
        full_name=full_name or email.split("@")[0],
        picture=picture,
        auth_provider="google",
        is_active=True,
        is_verified=True,
        pending_signup=False,
        tenant_id=tenant_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def create_user(
    email: str,
    password: str,
    full_name: Optional[str] = None,
    db: Session = None,
) -> User:
    """
    Create a new user with email and password
    
    Args:
        email: User email address
        password: Plain text password (will be hashed)
        full_name: User's full name
        db: Database session
        
    Returns:
        User object
    """
    if db is None:
        _db = SessionLocal()
        try:
            return _create_user_impl(email, password, full_name, _db)
        finally:
            _db.close()
    return _create_user_impl(email, password, full_name, db)


def _create_user_impl(
    email: str,
    password: str,
    full_name: Optional[str] = None,
    db: Session = None,
) -> User:
    hashed_password = get_password_hash(password)
    
    # Create tenant for new user
    tenant_id = str(uuid.uuid4())
    tenant = Tenant(
        id=tenant_id,
        name=f"{full_name or email.split('@')[0]}'s Organization",
        is_active=True
    )
    db.add(tenant)
    
    # Create new user
    new_user = User(
        id=str(uuid.uuid4()),
        email=email.lower(),
        full_name=full_name or email.split("@")[0],
        hashed_password=hashed_password,
        auth_provider="local",
        is_active=True,
        is_verified=False,  # Email verification can be added later
        pending_signup=False,
        tenant_id=tenant_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user
