"""Test script to verify configuration values"""
from core.config import get_settings

settings = get_settings()

print("=" * 60)
print("CONFIGURATION TEST")
print("=" * 60)
print(f"FRONTEND_URL: {settings.FRONTEND_URL}")
print(f"GOOGLE_CLIENT_ID: {settings.GOOGLE_CLIENT_ID[:20]}..." if settings.GOOGLE_CLIENT_ID else "GOOGLE_CLIENT_ID: Not set")
print(f"GOOGLE_REDIRECT_URI: {settings.GOOGLE_REDIRECT_URI}")
print(f"DATABASE_URL: {settings.DATABASE_URL}")
print("=" * 60)
