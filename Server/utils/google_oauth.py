"""
Google OAuth client utilities
"""
import httpx
from urllib.parse import urlencode
from typing import Optional, Dict, Any
from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class GoogleOAuthClient:
    """Google OAuth 2.0 client"""
    
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
        
        # Google OAuth URLs
        self.auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Get Google OAuth authorization URL
        
        Returns:
            Authorization URL string
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        
        query_string = urlencode(params)
        return f"{self.auth_url}?{query_string}"
    
    async def authenticate_with_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Exchange authorization code for user information
        
        Args:
            code: Authorization code from Google
            
        Returns:
            User information dictionary or None if failed
        """
        try:
            # Exchange code for access token
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    self.token_url,
                    data={
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": self.redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
                
                if token_response.status_code != 200:
                    logger.warning(f"Token exchange failed: {token_response.text}")
                    return None
                
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                if not access_token:
                    return None
                
                # Get user information
                userinfo_response = await client.get(
                    self.userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                
                if userinfo_response.status_code != 200:
                    logger.warning(f"Userinfo failed: {userinfo_response.text}")
                    return None
                
                return userinfo_response.json()
        
        except Exception as e:
            logger.error(f"OAuth error: {e}")
            return None


def get_google_oauth_client() -> GoogleOAuthClient:
    """Get Google OAuth client instance"""
    return GoogleOAuthClient()
