from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
from jose import jwt

from core.config import get_settings


settings = get_settings()


class GitHubAppService:
    @staticmethod
    def is_configured() -> bool:
        return bool(
            settings.GITHUB_APP_ID
            and settings.GITHUB_APP_PRIVATE_KEY
            and settings.GITHUB_APP_CLIENT_ID
            and settings.GITHUB_APP_CLIENT_SECRET
        )

    @staticmethod
    def _private_key() -> str:
        return settings.GITHUB_APP_PRIVATE_KEY.replace("\\n", "\n")

    @classmethod
    def build_app_jwt(cls) -> str:
        now = datetime.utcnow()
        payload = {
            "iat": int((now - timedelta(seconds=30)).timestamp()),
            "exp": int((now + timedelta(minutes=9)).timestamp()),
            "iss": settings.GITHUB_APP_ID,
        }
        return jwt.encode(payload, cls._private_key(), algorithm="RS256")

    @classmethod
    def get_installation_access_token(cls, github_installation_id: str) -> str:
        app_jwt = cls.build_app_jwt()
        url = f"https://api.github.com/app/installations/{github_installation_id}/access_tokens"
        response = requests.post(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {app_jwt}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        if not token:
            raise RuntimeError("GitHub installation token missing in response")
        return token

    @classmethod
    def list_installation_repositories(cls, github_installation_id: str) -> List[Dict[str, Any]]:
        token = cls.get_installation_access_token(github_installation_id)
        url = "https://api.github.com/installation/repositories"
        response = requests.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"token {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )
        response.raise_for_status()
        repos = response.json().get("repositories", [])
        result: List[Dict[str, Any]] = []
        for repo in repos:
            result.append(
                {
                    "id": str(repo.get("id")),
                    "name": repo.get("name"),
                    "full_name": repo.get("full_name"),
                    "owner": repo.get("owner", {}).get("login"),
                    "default_branch": repo.get("default_branch") or "main",
                    "private": bool(repo.get("private", True)),
                    "clone_url": repo.get("clone_url"),
                }
            )
        return result

    @classmethod
    def get_installation_metadata(cls, github_installation_id: str) -> Dict[str, Any]:
        app_jwt = cls.build_app_jwt()
        url = f"https://api.github.com/app/installations/{github_installation_id}"
        response = requests.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {app_jwt}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        account = data.get("account") or {}
        return {
            "github_installation_id": str(data.get("id") or github_installation_id),
            "account_login": account.get("login") or "unknown",
            "account_type": account.get("type") or None,
        }
