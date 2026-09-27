"""
Authentication Router - Email/Password + Google OAuth
FastAPI server: https://api.modelix.world
Frontend: https://run-time.in
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from datetime import datetime
from typing import Dict, Any
import hashlib
import hmac
import secrets
import time

from core.config import get_settings
from core.security import create_access_token, verify_password, get_password_hash
from db.models import User
from db.base import get_db
from sqlalchemy.orm import Session
from Schemas.user import (
    UserMeResponse,
    GoogleAuthRequestWithState,
    UserCreate,
    UserLogin,
    UserProfileUpdate,
)
from Schemas.token import TokenResponse, GoogleAuthUrlResponse, Token
from dependencies.auth import get_current_user, get_current_active_user
from crud.user import (
    get_user_by_id,
    get_user_by_email,
    create_google_user,
    create_user,
)
from utils.google_oauth import get_google_oauth_client

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()
_OAUTH_STATE_TTL_SECONDS = 900


def _oauth_state_signing_key() -> str:
    # Derive a scoped key from JWT secret to avoid adding a separate env var requirement.
    return f"{settings.JWT_SECRET_KEY}:google-oauth-state"


def _generate_oauth_state() -> str:
    ts = int(time.time())
    nonce = secrets.token_urlsafe(16)
    payload = f"{ts}.{nonce}"
    signature = hmac.new(
        _oauth_state_signing_key().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def _is_valid_oauth_state(state: str) -> bool:
    if not state:
        return False

    parts = state.split(".")
    if len(parts) != 3:
        return False

    ts_text, nonce, provided_sig = parts
    if not ts_text.isdigit() or not nonce:
        return False

    payload = f"{ts_text}.{nonce}"
    expected_sig = hmac.new(
        _oauth_state_signing_key().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return False

    age_seconds = int(time.time()) - int(ts_text)
    if age_seconds < 0 or age_seconds > _OAUTH_STATE_TTL_SECONDS:
        return False

    return True

# ==================== EMAIL/PASSWORD AUTHENTICATION ====================
@router.post("/signup", response_model=Token)
async def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user with email and password.
    
    **Request Body:**
    ```json
    {
        "email": "user@example.com",
        "password": "SecurePassword123",
        "full_name": "John Doe"
    }
    ```
    
    **Returns:**
    - Access token for immediate login
    """
    # Check if user already exists
    existing_user = get_user_by_email(user_data.email, db)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    new_user = create_user(
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
        db=db
    )
    
    # Create access token
    access_token = create_access_token(data={"sub": str(new_user.id)})
    
    return Token(
        access_token=access_token,
        token_type="bearer"
    )


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    **Request Body:**
    ```json
    {
        "email": "user@example.com",
        "password": "SecurePassword123"
    }
    ```
    
    **Returns:**
    - Access token
    """
    # Get user by email
    user = get_user_by_email(credentials.email, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not user.hashed_password or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return Token(
        access_token=access_token,
        token_type="bearer"
    )


# ==================== GET CURRENT USER ====================
@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get current authenticated user's information.
    
    **Authentication:**
    - Requires valid JWT token in Authorization header: `Bearer <token>`
    
    **Returns:**
    - User details including email, name, creation date, etc.
    """
    # Fetch full user details from database using the injected session
    user = get_user_by_id(current_user["id"], db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserMeResponse(
        id=str(user.id),
        email=user.email,
        name=user.full_name or user.email.split("@")[0],
        full_name=user.full_name,
        role="user",  # Default role
        created_at=user.created_at,
        picture=user.picture,
        phone_number=user.phone_number,
        linkedin_url=user.linkedin_url,
        bio=user.bio,
    )


@router.put("/profile", response_model=UserMeResponse)
async def update_profile(
    payload: UserProfileUpdate,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update current user's profile metadata."""
    user = get_user_by_id(current_user["id"], db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or user.full_name

    if payload.picture is not None:
        user.picture = payload.picture.strip() if payload.picture else None

    if payload.phone_number is not None:
        user.phone_number = payload.phone_number.strip() if payload.phone_number else None

    if payload.linkedin_url is not None:
        linkedin = payload.linkedin_url.strip()
        if linkedin and not (linkedin.startswith("http://") or linkedin.startswith("https://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LinkedIn URL must start with http:// or https://"
            )
        user.linkedin_url = linkedin or None

    if payload.bio is not None:
        user.bio = payload.bio.strip() if payload.bio else None

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return UserMeResponse(
        id=str(user.id),
        email=user.email,
        name=user.full_name or user.email.split("@")[0],
        full_name=user.full_name,
        role="user",
        created_at=user.created_at,
        picture=user.picture,
        phone_number=user.phone_number,
        linkedin_url=user.linkedin_url,
        bio=user.bio,
    )



# ==================== GOOGLE OAUTH ====================
@router.get("/google", response_model=GoogleAuthUrlResponse)
async def get_google_auth_url():
    """
    Get the Google OAuth authorization URL.
    
    **Returns:**
    ```json
    {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
    }
    ```
    
    **Usage:**
    1. Frontend calls this endpoint
    2. Frontend redirects user to the returned `auth_url`
    3. User authorizes on Google
    4. Google redirects back to `/auth/google/callback`
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET or not settings.GOOGLE_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured. Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI environment variables."
        )
    
    oauth_client = get_google_oauth_client()
    state = _generate_oauth_state()
    auth_url = oauth_client.get_authorization_url(state=state)
    
    return GoogleAuthUrlResponse(auth_url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str = Query(None),
    state: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    Handle Google OAuth callback.
    
    **Query Parameters:**
    - code: Authorization code from Google
    - state: Optional state parameter for CSRF protection
    
    **Flow:**
    1. Google redirects here after user authorization with 'code'
    2. Backend exchanges code for user info
    3. Backend creates/finds user in database
    4. Backend redirects to frontend with access token in URL fragment
    
    **Returns:**
    - Redirect to frontend with access_token in URL fragment
    """
    try:
        # Get frontend URL from settings
        frontend_url = settings.FRONTEND_URL
        
        if not code:
            # Redirect to frontend login page with error
            return RedirectResponse(
                url=f"{frontend_url}/login?error=no_code",
                status_code=status.HTTP_302_FOUND
            )

        if not state or not _is_valid_oauth_state(state):
            return RedirectResponse(
                url=f"{frontend_url}/login?error=invalid_state",
                status_code=status.HTTP_302_FOUND,
            )
        
        # Exchange code for user info
        oauth_client = get_google_oauth_client()
        user_info = await oauth_client.authenticate_with_code(code)
        
        if not user_info:
            # Redirect to frontend login page with error
            return RedirectResponse(
                url=f"{frontend_url}/login?error=auth_failed",
                status_code=status.HTTP_302_FOUND
            )
        
        # Extract user information
        email = user_info.get("email")
        google_id = user_info.get("id")
        full_name = user_info.get("name")
        picture = user_info.get("picture")
        
        if not email:
            # Redirect to frontend login page with error
            return RedirectResponse(
                url=f"{frontend_url}/login?error=no_email",
                status_code=status.HTTP_302_FOUND
            )
        
        # Create or get user (sync function — no await)
        user = create_google_user(
            email=email,
            google_id=google_id,
            full_name=full_name,
            picture=picture,
            db=db,
        )
        
        # Create access token
        access_token = create_access_token(data={"sub": str(user.id)})
        
        # Redirect to frontend with token in URL fragment (hash)
        # Using fragment (#) instead of query (?) keeps token out of server logs
        redirect_url = f"{frontend_url}/auth/callback#access_token={access_token}&token_type=bearer"
        
        return RedirectResponse(
            url=redirect_url,
            status_code=status.HTTP_302_FOUND
        )
    
    except HTTPException as e:
        # Redirect to frontend login page with error
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=http_error",
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        # Redirect to frontend login page with error
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=server_error",
            status_code=status.HTTP_302_FOUND
        )


@router.get("/callback", response_class=HTMLResponse)
async def auth_callback():
    """
    OAuth callback handler - displays HTML page that extracts token from URL hash.
    This is a fallback for when frontend doesn't handle the callback.

    **Returns:**
    HTML page that extracts access_token from URL hash and redirects to frontend
    """
    frontend_url = settings.FRONTEND_URL
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authenticating - Nexarch</title>
    <style>
        :root {
            --color-cream: #F5F0E1;
            --color-cream-dark: #E8E0CC;
            --color-black: #000000;
            --color-yellow: #FFD700;
            --color-gray: #666666;
            --font-display: 'Bebas Neue', Impact, 'Arial Black', sans-serif;
            --font-body: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: var(--font-body);
            background-color: var(--color-cream);
            color: var(--color-black);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            overflow: hidden;
            position: relative;
        }
        .auth-page {
            width: 100%;
            max-width: 1000px;
            position: relative;
            z-index: 2;
        }
        .auth-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 3rem;
            width: 100%;
            align-items: center;
        }
        .auth-card {
            background-color: var(--color-cream);
            border: 2px solid var(--color-black);
            padding: 3rem;
            box-shadow: 8px 8px 0 var(--color-black);
            text-align: center;
        }
        .auth-logo {
            display: inline-block;
            font-family: var(--font-display);
            font-size: 1.25rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            background-color: var(--color-black);
            color: var(--color-cream);
            padding: 0.2rem 0.5rem;
            margin-bottom: 1rem;
        }
        .auth-title {
            font-family: var(--font-display);
            font-size: clamp(2rem, 6vw, 3.5rem);
            font-weight: 400;
            text-transform: uppercase;
            letter-spacing: 0.02em;
            line-height: 0.9;
            margin-bottom: 1rem;
        }
        .auth-loading-spinner {
            display: flex;
            justify-content: center;
            margin: 1.25rem 0;
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--color-cream-dark);
            border-top-color: var(--color-black);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .status {
            font-size: 0.95rem;
            color: var(--color-gray);
            line-height: 1.6;
        }
        .auth-subtitle {
            color: var(--color-gray);
            font-size: 0.95rem;
            margin-top: 0.75rem;
            line-height: 1.6;
        }
        .success {
            color: var(--color-black);
            font-weight: 700;
        }
        .error {
            color: #c62828;
            font-weight: 700;
        }
        .auth-decoration {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }
        .auth-decoration__grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 4px;
            max-width: 180px;
        }
        .auth-decoration__cell {
            width: 40px;
            height: 40px;
            background-color: var(--color-cream-dark);
            border: 1px solid var(--color-cream-dark);
        }
        .auth-decoration__cell:nth-child(odd) {
            background-color: var(--color-yellow);
            opacity: 0.3;
        }
        .auth-decoration__cell:nth-child(3n) {
            background-color: var(--color-black);
            opacity: 0.1;
        }
        .auth-decoration__title {
            font-family: var(--font-display);
            font-size: clamp(2rem, 5vw, 3rem);
            line-height: 1;
            color: var(--color-cream-dark);
            -webkit-text-stroke: 1px var(--color-black);
            text-transform: uppercase;
        }
        .auth-decoration__subtitle {
            color: var(--color-gray);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.08em;
        }
        .halftone-corner {
            position: absolute;
            width: 160px;
            height: 160px;
            background-image: radial-gradient(circle, var(--color-black) 1.5px, transparent 1.5px);
            background-size: 6px 6px;
            opacity: 0.12;
            z-index: 1;
            pointer-events: none;
        }
        .halftone-corner--top-right {
            top: 0;
            right: 0;
            mask-image: radial-gradient(circle at top right, black 0%, transparent 70%);
            -webkit-mask-image: radial-gradient(circle at top right, black 0%, transparent 70%);
        }
        .halftone-corner--bottom-left {
            bottom: 0;
            left: 0;
            mask-image: radial-gradient(circle at bottom left, black 0%, transparent 70%);
            -webkit-mask-image: radial-gradient(circle at bottom left, black 0%, transparent 70%);
        }
        @media (max-width: 768px) {
            .auth-container {
                grid-template-columns: 1fr;
                gap: 1.5rem;
            }
            .auth-decoration {
                display: none;
            }
            .auth-card {
                padding: 2rem;
            }
        }
        @media (max-width: 480px) {
            body {
                padding: 1rem;
            }
            .auth-card {
                padding: 1.5rem;
                box-shadow: 4px 4px 0 var(--color-black);
            }
        }
    </style>
</head>
<body>
    <div class="halftone-corner halftone-corner--top-right"></div>
    <div class="halftone-corner halftone-corner--bottom-left"></div>

    <div class="auth-page">
        <div class="auth-container">
            <div class="auth-card">
                <div class="auth-logo">NEXARCH</div>
                <h1 class="auth-title">Authenticating</h1>
                <div class="auth-loading-spinner">
                    <div class="spinner"></div>
                </div>
                <p id="status" class="status">Please wait while we complete your sign in...</p>
                <p class="auth-subtitle">Redirecting to your dashboard securely</p>
            </div>

            <div class="auth-decoration" aria-hidden="true">
                <div class="auth-decoration__grid">
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                    <div class="auth-decoration__cell"></div>
                </div>
                <div>
                    <div class="auth-decoration__title">Modelix</div>
                    <div class="auth-decoration__subtitle">Secure Access Gateway</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        const accessToken = params.get('access_token');
        const tokenType = params.get('token_type');
        const error = new URLSearchParams(window.location.search).get('error');

        const statusEl = document.getElementById('status');

        if (error) {
            statusEl.innerHTML = '<span class="error">Authentication failed: ' + error + '</span>';
            setTimeout(() => {
                window.location.href = '__FRONTEND_URL__/login?error=' + error;
            }, 2000);
        } else if (accessToken) {
            statusEl.innerHTML = '<span class="success">Login successful</span><br><span>Redirecting to dashboard...</span>';
            setTimeout(() => {
                window.location.href = '__FRONTEND_URL__/auth/callback#access_token=' + accessToken + '&token_type=' + (tokenType || 'bearer');
            }, 900);
        } else {
            statusEl.innerHTML = '<span class="error">No token received</span>';
            setTimeout(() => {
                window.location.href = '__FRONTEND_URL__/login';
            }, 2000);
        }
    </script>
</body>
</html>
    """
    return html_content.replace("__FRONTEND_URL__", frontend_url.rstrip("/"))


@router.post("/google/signin", response_model=TokenResponse)
async def google_signin(
    request: GoogleAuthRequestWithState,
    db: Session = Depends(get_db),
):
    """
    Alternative Google login endpoint that returns token directly (no redirect).
    
    **Request Body:**
    ```json
    {
        "code": "google_authorization_code",
        "state": "optional_state_parameter"
    }
    ```
    
    **Returns:**
    - access_token: JWT token for authentication
    - token_type: "bearer"
    - user: User information
    
    **Usage:**
    Use this endpoint if your frontend can't handle OAuth redirects
    and prefers to handle the Google authorization code directly.
    """
    try:
        if not request.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code not provided"
            )

        if not request.state or not _is_valid_oauth_state(request.state):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OAuth state"
            )
        
        # Exchange code for user info
        oauth_client = get_google_oauth_client()
        user_info = await oauth_client.authenticate_with_code(request.code)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to authenticate with Google"
            )
        
        # Extract user information
        email = user_info.get("email")
        google_id = user_info.get("id")
        full_name = user_info.get("name")
        picture = user_info.get("picture")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by Google"
            )
        
        # Create or get user (sync function — no await)
        user = create_google_user(
            email=email,
            google_id=google_id,
            full_name=full_name,
            picture=picture,
            db=db,
        )
        
        # Create access token
        access_token = create_access_token(data={"sub": str(user.id)})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "picture": user.picture,
                "auth_provider": user.auth_provider,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google authentication failed. Please try again."
        )


# ==================== LOGOUT ====================
@router.post("/logout")
async def logout():
    """
    Client-side logout - no server-side action needed for JWT.
    
    **Note:**
    Since we use stateless JWT tokens, logout is handled client-side
    by removing the token from storage. This endpoint exists for
    consistency with the API spec.
    
    **Returns:**
    - Success message
    """
    return {"message": "Logged out successfully. Please remove the token from client storage."}


# ==================== GOOGLE OAUTH STATUS ====================
@router.get("/google/status")
async def google_oauth_status():
    """
    Check Google OAuth configuration status for debugging.
    
    **Returns:**
    - Status information about Google OAuth configuration
    """
    has_client_id = bool(settings.GOOGLE_CLIENT_ID)
    has_client_secret = bool(settings.GOOGLE_CLIENT_SECRET)
    has_redirect_uri = bool(settings.GOOGLE_REDIRECT_URI)
    
    is_configured = has_client_id and has_client_secret and has_redirect_uri
    
    return {
        "configured": is_configured,
        "has_client_id": has_client_id,
        "has_client_secret": has_client_secret,
        "has_redirect_uri": has_redirect_uri,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI if has_redirect_uri else None,
        "message": "Google OAuth is properly configured" if is_configured else "Google OAuth is not fully configured"
    }


# ==================== DEBUG TOKEN ====================
@router.get("/debug-token")
async def debug_token(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Debug endpoint to test token validation.
    
    This will help identify authentication issues.
    
    **Authentication:**
    - Requires valid JWT token in Authorization header: `Bearer <token>`
    
    **Returns:**
    - Token validation details and user information
    """
    return {
        "valid": True,
        "message": "Token is valid and authenticated",
        "user_id": current_user.get("id"),
        "email": current_user.get("email"),
        "auth_provider": current_user.get("auth_provider"),
        "is_active": current_user.get("is_active"),
        "is_verified": current_user.get("is_verified")
    }

