"""
Production-Ready Configuration with Azure OpenAI
"""
import os
import json
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional, List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Nexarch"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "sqlite:///./nexarch.db"  # Change to PostgreSQL for production
    
    # Azure Cache for Redis Configuration
    # Format: redis://[:password]@host:port/db or rediss://[:password]@host:port/db (SSL)
    # Example Azure: rediss://:password@your-cache.redis.cache.windows.net:6380/0
    REDIS_URL: Optional[str] = None
    REDIS_HOST: Optional[str] = None  # Alternative: specify host/port separately
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = True  # Azure Cache for Redis uses SSL by default
    REDIS_DB: int = 0
    CACHE_TTL_SECONDS: int = 300  # 5 minutes default TTL
    # (CACHE_ENABLED is an older alias — use ENABLE_CACHING feature flag below)
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4"
    AZURE_OPENAI_DEPLOYMENT_GPT5: str = "gpt-5.3-chat"
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_TEMPERATURE: float = 0.7
    AZURE_OPENAI_MAX_TOKENS: int = 16384
    
    # Google Gemini API Configuration
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    
    # Authentication & Security
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    API_KEY_PREFIX: str = "nex_"
    ADMIN_SECRET_KEY: str = ""  # Set to a strong secret to enable admin API endpoints
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None
    FRONTEND_URL: str = "https://run-time.in"  # Frontend URL for OAuth redirects

    # GitHub App Integration
    GITHUB_APP_ID: str = ""
    GITHUB_APP_CLIENT_ID: str = ""
    GITHUB_APP_CLIENT_SECRET: str = ""
    GITHUB_APP_PRIVATE_KEY: str = ""
    GITHUB_APP_SLUG: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""

    # System Architecture / Repository Processing
    REPO_WORKSPACE_ROOT: str = "./storage"
    MONOREPO_MAX_SIZE_MB: int = 200
    SYSTEM_ARCH_DEFAULT_COST_WEIGHT: float = 30.0
    SYSTEM_ARCH_DEFAULT_SCALABILITY_WEIGHT: float = 35.0
    SYSTEM_ARCH_DEFAULT_PERFORMANCE_WEIGHT: float = 35.0
    SYSTEM_ARCH_AI_MODE: str = "async"  # async|sync
    SYSTEM_ARCH_ALLOW_SYNC_FALLBACK: bool = True
    SYSTEM_ARCH_SYNC_TARGET_SECONDS: int = 10
    SYSTEM_ARCH_GRAPH_SERVICE_LIMIT: int = 12
    SYSTEM_ARCH_DEEP_GRAPH_SERVICE_LIMIT: int = 24
    SYSTEM_ARCH_DEEP_GRAPH_FILE_THRESHOLD: int = 1200
    ALPHA_CODE_TIMEOUT_MINUTES: int = 120
    ALPHA_SANDBOX_MAX_CONCURRENT_PER_USER: int = 5
    ALPHA_SANDBOX_IDLE_TIMEOUT_MINUTES: int = 15
    ALPHA_SANDBOX_MAX_UPLOAD_FILES: int = 50
    ALPHA_SANDBOX_MAX_UPLOAD_TOTAL_MB: int = 25
    ALPHA_SANDBOX_COMMAND_TIMEOUT_SECONDS: int = 900
    ALPHA_SANDBOX_AUTOFIX_MAX_ATTEMPTS: int = 10
    ALPHA_SANDBOX_RUNTIME_BACKEND: str = "local"  # local|acr
    ALPHA_SANDBOX_ACR_LOGIN_SERVER: str = ""
    ALPHA_SANDBOX_ACR_USERNAME: str = ""
    ALPHA_SANDBOX_ACR_PASSWORD: str = ""
    ALPHA_SANDBOX_ACR_IMAGE: str = "nexarch/sandbox-runner:latest"
    ALPHA_SANDBOX_ACR_IMAGE_PULL_POLICY: str = "if_not_present"  # always|if_not_present

    # SMTP Notifications
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True
    
    # Rate Limiting (per tenant)
    RATE_LIMIT_PER_MINUTE: int = 1000
    
    # Metrics thresholds
    HIGH_LATENCY_THRESHOLD_MS: int = 1000
    HIGH_ERROR_RATE_THRESHOLD: float = 0.05
    MAX_SYNC_CHAIN_DEPTH: int = 5
    MAX_FAN_OUT: int = 10
    
    # AI Generation Settings
    ENABLE_AI_GENERATION: bool = True
    MAX_WORKFLOW_ALTERNATIVES: int = 5
    
    # CORS
    # Supports JSON array or comma-separated values in .env
    # Examples:
    # CORS_ORIGINS=["https://run-time.in","http://localhost:3000"]
    # CORS_ORIGINS=https://run-time.in,http://localhost:3000
    CORS_ORIGINS: str = "https://run-time.in,http://localhost:3000,http://127.0.0.1:3000"
    
    # Feature Flags
    ENABLE_MULTI_TENANT: bool = True
    ENABLE_CACHING: bool = True
    ENABLE_RATE_LIMITING: bool = True
    
    def get_redis_url(self) -> Optional[str]:
        """Build Redis URL from components if REDIS_URL not provided"""
        if self.REDIS_URL:
            return self.REDIS_URL
        
        if self.REDIS_HOST and self.REDIS_PASSWORD:
            protocol = "rediss" if self.REDIS_SSL else "redis"
            return f"{protocol}://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        
        return None

    def get_cors_origins(self) -> List[str]:
        """Return normalized CORS origins from env configuration."""
        raw = (self.CORS_ORIGINS or "").strip()
        default_origins = [
            "https://run-time.in",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        if not raw:
            return default_origins

        # JSON array support
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            except json.JSONDecodeError:
                pass

        # Comma-separated fallback
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        merged = []
        seen = set()
        for origin in default_origins + origins:
            cleaned = origin.strip()
            if cleaned and cleaned not in seen:
                merged.append(cleaned)
                seen.add(cleaned)
        return merged or default_origins

    def has_acr_sandbox_config(self) -> bool:
        """Return True when ACR auth + image settings are available for sandbox runtime."""
        return bool(
            self.ALPHA_SANDBOX_ACR_LOGIN_SERVER
            and self.ALPHA_SANDBOX_ACR_USERNAME
            and self.ALPHA_SANDBOX_ACR_PASSWORD
            and self.ALPHA_SANDBOX_ACR_IMAGE
        )
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # silently ignore unknown env vars (e.g. legacy CACHE_ENABLED)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Singleton instance
settings = get_settings()
