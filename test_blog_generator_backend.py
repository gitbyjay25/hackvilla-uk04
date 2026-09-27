"""Smoke test for the blog generator demo backend.

Expected flow:
1. Start the backend separately with uvicorn blog_generator_backend:app
2. Run this script to verify the API and the AI generation path

Run:
    python test_blog_generator_backend.py
"""

from __future__ import annotations

import os
from typing import Any, Dict

import requests


BASE_URL = os.getenv("BLOG_BACKEND_URL", "http://127.0.0.1:8010")


def request_json(method: str, path: str, *, body: Dict[str, Any] | None = None, timeout: int = 45):
    url = f"{BASE_URL}{path}"
    response = requests.request(method, url, json=body, timeout=timeout)
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    return response.status_code, payload


def assert_ok(name: str, status: int, expected: int, payload: Any) -> None:
    ok = status == expected
    print(f"{'PASS' if ok else 'FAIL'} {name}: status={status}")
    if not ok:
        print(payload)
        raise SystemExit(1)


def main() -> None:
    results = []

    status, payload = request_json("GET", "/health")
    assert_ok("health", status, 200, payload)
    results.append(("health", status == 200))

    status, payload = request_json(
        "POST",
        "/blog-posts/generate",
        body={
            "topic": "How Nexarch helps a blog generator platform observe AI content workflows",
            "audience": "platform engineers",
            "tone": "clear and pragmatic",
            "keywords": ["telemetry", "workflow", "Azure OpenAI", "SDK"],
            "target_length_words": 900,
        },
    )
    assert_ok("generate_blog", status, 200, payload)
    results.append(("generate_blog", status == 200))

    post_id = payload["id"]
    print(f"Generated post id: {post_id}")
    print(f"Model used: {payload['model_used']}")

    status, payload = request_json("GET", f"/blog-posts/{post_id}")
    assert_ok("get_blog", status, 200, payload)
    results.append(("get_blog", status == 200))

    status, payload = request_json("POST", f"/blog-posts/{post_id}/publish")
    assert_ok("publish_blog", status, 200, payload)
    results.append(("publish_blog", status == 200))

    status, payload = request_json("GET", "/blog-posts")
    assert_ok("list_blogs", status, 200, payload)
    results.append(("list_blogs", status == 200))

    status, payload = request_json("DELETE", f"/blog-posts/{post_id}")
    assert_ok("delete_blog", status, 200, payload)
    results.append(("delete_blog", status == 200))

    passed = sum(1 for _, ok in results if ok)
    failed = len(results) - passed
    print(f"TOTAL={len(results)} PASS={passed} FAIL={failed}")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
