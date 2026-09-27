"""Quick connectivity test for Azure OpenAI deployment gpt-5.3-chat.

Usage:
  python Server/tests/test_gpt53_azure_script.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import requests


def _load_env_fallback() -> None:
    """Load key=value pairs from Server/.env only for missing vars."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.abspath(env_path)
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def main() -> int:
    _load_env_fallback()

    endpoint = _required_env("AZURE_OPENAI_ENDPOINT").rstrip("/")
    api_key = _required_env("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview").strip() or "2024-02-15-preview"

    # Explicitly test the requested deployment first.
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT5", "").strip() or "gpt-5.3-chat"

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    payload = {
        "messages": [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "Reply with: GPT-5.3 Azure test OK and current UTC date."},
        ],
        "temperature": 0.2,
        "max_tokens": 16000,
    }

    started = datetime.now(timezone.utc).isoformat()
    print("[TEST] Azure OpenAI deployment connectivity")
    print(f"[INFO] endpoint={endpoint}")
    print(f"[INFO] deployment={deployment}")
    print(f"[INFO] api_version={api_version}")

    try:
        response = requests.post(
            url,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
    except requests.RequestException as exc:
        print(f"[FAIL] request_error={exc}")
        return 2

    # GPT-5 deployments can reject `max_tokens` and require `max_completion_tokens`.
    if not response.ok:
        try:
            err = response.json().get("error", {})
        except Exception:
            err = {}
        if err.get("param") == "max_tokens" and err.get("code") == "unsupported_parameter":
            compat_payload = {
                "messages": payload["messages"],
                "temperature": payload["temperature"],
                "max_completion_tokens": 16000,
            }
            try:
                response = requests.post(
                    url,
                    headers={"api-key": api_key, "Content-Type": "application/json"},
                    json=compat_payload,
                    timeout=60,
                )
                print("[INFO] Retried with max_completion_tokens compatibility mode")
            except requests.RequestException as exc:
                print(f"[FAIL] retry_request_error={exc}")
                return 2

    # Some GPT-5 deployments only allow default temperature.
    if not response.ok:
        try:
            err = response.json().get("error", {})
        except Exception:
            err = {}
        if err.get("param") == "temperature" and err.get("code") == "unsupported_value":
            compat_payload = {
                "messages": payload["messages"],
                "max_completion_tokens": 16000,
            }
            try:
                response = requests.post(
                    url,
                    headers={"api-key": api_key, "Content-Type": "application/json"},
                    json=compat_payload,
                    timeout=60,
                )
                print("[INFO] Retried with default temperature compatibility mode")
            except requests.RequestException as exc:
                print(f"[FAIL] retry_temperature_request_error={exc}")
                return 2

    print(f"[INFO] http_status={response.status_code}")

    if not response.ok:
        detail = response.text
        try:
            detail = json.dumps(response.json(), indent=2)
        except Exception:
            pass
        print("[FAIL] Azure OpenAI call failed")
        print(detail)
        return 1

    try:
        body = response.json()
    except Exception as exc:
        print(f"[FAIL] invalid_json_response={exc}")
        print(response.text[:2000])
        return 1

    content = (
        body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    usage = body.get("usage", {})
    print("[PASS] Azure OpenAI call succeeded")
    print(f"[INFO] started_utc={started}")
    print(f"[INFO] prompt_tokens={usage.get('prompt_tokens')}")
    print(f"[INFO] completion_tokens={usage.get('completion_tokens')}")
    print(f"[INFO] total_tokens={usage.get('total_tokens')}")
    print("[OUTPUT]")
    print(content or "<empty>")

    return 0


if __name__ == "__main__":
    sys.exit(main())
