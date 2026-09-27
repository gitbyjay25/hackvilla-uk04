"""End-to-end test: Nexarch backend + blog generator backend + SDK telemetry.

Steps:
1) Log in to Nexarch backend with env-provided credentials.
2) Create a fresh API key for SDK telemetry.
3) Start the blog generator backend with the SDK exporting to Nexarch.
4) Exercise the blog API to generate telemetry.
5) Verify Nexarch backend endpoints see the data.
6) Revoke the API key and stop the blog backend.

Env vars:
    NEXARCH_BASE_URL   (default: https://api.modelix.world)
    NEXARCH_EMAIL      (required)
    NEXARCH_PASSWORD   (required)
    BLOG_BACKEND_URL   (default: http://127.0.0.1:8010)
    NEXARCH_PROJECT_NAME (default: blog-e2e-project)
    NEXARCH_STRESS_PROFILE (default: medium; options: light, medium, heavy, extreme)
    NEXARCH_TELEMETRY_BURST (optional numeric override for request count)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, Tuple

import requests


BASE_URL = os.getenv("NEXARCH_BASE_URL", "https://api.modelix.world").rstrip("/")
BLOG_URL = os.getenv("BLOG_BACKEND_URL", "http://127.0.0.1:8010").rstrip("/")
EMAIL = os.getenv("NEXARCH_EMAIL", "")
PASSWORD = os.getenv("NEXARCH_PASSWORD", "")
PROJECT_NAME = os.getenv("NEXARCH_PROJECT_NAME", "blog-e2e-project")
STRESS_PROFILE = os.getenv("NEXARCH_STRESS_PROFILE", "medium").strip().lower() or "medium"

_STRESS_PROFILES: Dict[str, Dict[str, int]] = {
    "light": {
        "requests": 80,
        "root_every": 4,
        "list_every": 6,
        "detail_every": 9,
    },
    "medium": {
        "requests": 220,
        "root_every": 3,
        "list_every": 5,
        "detail_every": 7,
    },
    "heavy": {
        "requests": 500,
        "root_every": 2,
        "list_every": 3,
        "detail_every": 5,
    },
    "extreme": {
        "requests": 900,
        "root_every": 1,
        "list_every": 2,
        "detail_every": 3,
    },
}


def _resolve_stress_profile() -> Dict[str, int]:
    config = dict(_STRESS_PROFILES.get(STRESS_PROFILE, _STRESS_PROFILES["medium"]))
    override = os.getenv("NEXARCH_TELEMETRY_BURST", "").strip()
    if override:
        try:
            config["requests"] = max(1, int(override))
        except ValueError:
            raise SystemExit(
                "Invalid NEXARCH_TELEMETRY_BURST value. Expected an integer. "
                f"Got: {override!r}"
            )
    return config


def request_json(
    method: str,
    url: str,
    *,
    headers=None,
    body=None,
    timeout: int = 30,
    retries: int = 0,
) -> Tuple[int, Any]:
    attempts = max(0, int(retries)) + 1
    last_exc: Exception | None = None
    for idx in range(attempts):
        try:
            response = requests.request(method, url, headers=headers, json=body, timeout=timeout)
            try:
                payload = response.json()
            except Exception:
                payload = response.text
            return response.status_code, payload
        except requests.Timeout as exc:
            last_exc = exc
            if idx < attempts - 1:
                time.sleep(1)
                continue
            raise

    raise RuntimeError(f"Request failed after {attempts} attempts: {last_exc}")


def assert_status(name: str, status: int, expected: int, payload: Any) -> None:
    ok = status == expected
    print(f"{'PASS' if ok else 'FAIL'} {name}: status={status}")
    if not ok:
        print(payload)
        raise SystemExit(1)


def login() -> str:
    if not EMAIL or not PASSWORD:
        raise SystemExit("Missing NEXARCH_EMAIL or NEXARCH_PASSWORD in environment.")

    status, payload = request_json(
        "POST",
        f"{BASE_URL}/auth/login",
        body={"email": EMAIL, "password": PASSWORD},
    )
    assert_status("auth_login", status, 200, payload)
    return payload.get("access_token", "")


def create_api_key(bearer: Dict[str, str]) -> str:
    status, payload = request_json(
        "POST",
        f"{BASE_URL}/api/v1/api-keys/",
        headers=bearer,
        body={"name": "blog-demo-sdk"},
    )
    assert_status("create_api_key", status, 200, payload)
    return payload.get("key", "")


def revoke_api_key(bearer: Dict[str, str], api_key: str) -> None:
    preview = api_key.split("...", 1)[0][:8]
    status, payload = request_json(
        "DELETE",
        f"{BASE_URL}/api/v1/api-keys/{preview}",
        headers=bearer,
    )
    assert_status("revoke_api_key", status, 200, payload)


def _tail_file(path: str, lines: int = 60) -> str:
    if not os.path.exists(path):
        return "(no backend log file found)"
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.readlines()
    return "".join(content[-lines:]).strip()


def wait_for_blog_health(server: subprocess.Popen, log_path: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if server.poll() is not None:
            tail = _tail_file(log_path)
            raise SystemExit(
                "Blog backend exited before becoming healthy. "
                f"Exit code={server.returncode}.\nRecent log output:\n{tail}"
            )
        try:
            status, _payload = request_json("GET", f"{BLOG_URL}/health")
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    tail = _tail_file(log_path)
    raise SystemExit(f"Blog backend did not become healthy in time.\nRecent log output:\n{tail}")


def exercise_blog_api() -> str:
    stress = _resolve_stress_profile()
    print(
        "INFO telemetry_stress_profile="
        f"{STRESS_PROFILE if STRESS_PROFILE in _STRESS_PROFILES else 'medium'} "
        f"requests={stress['requests']} root_every={stress['root_every']} "
        f"list_every={stress['list_every']} detail_every={stress['detail_every']}"
    )

    status, payload = request_json(
        "POST",
        f"{BLOG_URL}/blog-posts/generate",
        body={
            "topic": "Telemetry-driven blog generation with Nexarch",
            "audience": "platform engineers",
            "tone": "clear and pragmatic",
            "keywords": ["telemetry", "observability", "Azure OpenAI"],
            "target_length_words": 900,
        },
    )
    assert_status("blog_generate", status, 200, payload)
    post_id = payload["id"]

    status, payload = request_json("GET", f"{BLOG_URL}/blog-posts/{post_id}")
    assert_status("blog_get", status, 200, payload)

    status, payload = request_json("POST", f"{BLOG_URL}/blog-posts/{post_id}/publish")
    assert_status("blog_publish", status, 200, payload)

    status, payload = request_json("GET", f"{BLOG_URL}/blog-posts")
    assert_status("blog_list", status, 200, payload)

    status, payload = request_json("DELETE", f"{BLOG_URL}/blog-posts/{post_id}")
    assert_status("blog_delete", status, 200, payload)

    # Generate sustained traffic so project analytics and rollups have enough signal.
    for i in range(stress["requests"]):
        request_json("GET", f"{BLOG_URL}/health")
        if i % stress["root_every"] == 0:
            request_json("GET", f"{BLOG_URL}/")
        if i % stress["list_every"] == 0:
            request_json("GET", f"{BLOG_URL}/blog-posts")
        if i % stress["detail_every"] == 0:
            request_json("GET", f"{BLOG_URL}/blog-posts/{post_id}")

    return post_id


def verify_nexarch_backend(api_key: str, bearer: Dict[str, str]) -> None:
    api_headers = {"X-API-Key": api_key}

    checks = [
        ("ingest_stats", "GET", f"{BASE_URL}/api/v1/ingest/stats", api_headers, 200),
        ("discoveries", "GET", f"{BASE_URL}/api/v1/ingest/architecture-discoveries", api_headers, 200),
        ("dashboard_overview", "GET", f"{BASE_URL}/api/v1/dashboard/overview", bearer, 200),
        ("dashboard_architecture_map", "GET", f"{BASE_URL}/api/v1/dashboard/architecture-map", bearer, 200),
        ("dashboard_services", "GET", f"{BASE_URL}/api/v1/dashboard/services", bearer, 200),
        ("dashboard_dependencies", "GET", f"{BASE_URL}/api/v1/dashboard/dependencies", bearer, 200),
        ("dashboard_bottlenecks", "GET", f"{BASE_URL}/api/v1/dashboard/bottlenecks", bearer, 200),
        ("dashboard_health", "GET", f"{BASE_URL}/api/v1/dashboard/health", bearer, 200),
        ("dashboard_trends", "GET", f"{BASE_URL}/api/v1/dashboard/trends", bearer, 200),
        ("dashboard_insights", "GET", f"{BASE_URL}/api/v1/dashboard/insights", bearer, 200),
        ("dashboard_recommendations", "GET", f"{BASE_URL}/api/v1/dashboard/recommendations", bearer, 200),
        ("dashboard_workflows", "GET", f"{BASE_URL}/api/v1/dashboard/workflows", bearer, 200),
        ("dashboard_projects", "GET", f"{BASE_URL}/api/v1/dashboard/projects", bearer, 200),
        ("system_stats", "GET", f"{BASE_URL}/api/v1/system/stats", bearer, 200),
        ("stream_status", "GET", f"{BASE_URL}/api/v1/stream/status", None, 200),
    ]

    ingest_payload = None
    dashboard_projects_payload = None
    for name, method, url, headers, expected in checks:
        timeout = 30
        retries = 0
        if name in {"dashboard_recommendations", "dashboard_workflows", "dashboard_insights"}:
            timeout = 120
            retries = 1
        status, payload = request_json(method, url, headers=headers, timeout=timeout, retries=retries)
        assert_status(name, status, expected, payload)
        if name == "ingest_stats":
            ingest_payload = payload
            print(json.dumps(payload, indent=2, default=str))
        if name == "dashboard_projects":
            dashboard_projects_payload = payload

    if isinstance(ingest_payload, dict):
        span_count = int(ingest_payload.get("spans", 0) or 0)
        if span_count < 50:
            raise SystemExit(f"Expected at least 50 spans after traffic burst, got {span_count}")

    if not isinstance(dashboard_projects_payload, dict):
        raise SystemExit("Dashboard projects payload is invalid")

    projects = dashboard_projects_payload.get("projects", [])
    if not isinstance(projects, list) or not projects:
        raise SystemExit("No projects returned from dashboard projects endpoint")

    target_project = None
    for item in projects:
        if not isinstance(item, dict):
            continue
        if item.get("name") == PROJECT_NAME:
            target_project = item
            break
    if target_project is None:
        target_project = projects[0]

    project_id = target_project.get("id")
    if not project_id:
        raise SystemExit("Project id missing from dashboard projects response")

    status, payload = request_json(
        "GET",
        f"{BASE_URL}/api/v1/dashboard/projects/{project_id}",
        headers=bearer,
    )
    assert_status("dashboard_project_detail", status, 200, payload)

    overview = payload.get("overview", {}) if isinstance(payload, dict) else {}
    summary = overview.get("summary", {}) if isinstance(overview, dict) else {}
    total_requests = int(summary.get("total_requests", 0) or 0)
    if total_requests <= 0:
        raise SystemExit("Project detail has no request analytics yet")

    print(
        json.dumps(
            {
                "selected_project": {
                    "id": project_id,
                    "name": target_project.get("name"),
                    "span_count": target_project.get("span_count"),
                    "service_count": target_project.get("service_count"),
                },
                "project_overview_summary": summary,
            },
            indent=2,
            default=str,
        )
    )


def main() -> None:
    token = login()
    if not token:
        raise SystemExit("Login did not return an access token.")
    bearer = {"Authorization": f"Bearer {token}"}

    api_key = create_api_key(bearer)
    if not api_key:
        raise SystemExit("API key creation failed.")

    env = os.environ.copy()
    env["NEXARCH_SDK_API_KEY"] = api_key
    env["NEXARCH_HTTP_ENDPOINT"] = BASE_URL
    env["NEXARCH_PROJECT_NAME"] = PROJECT_NAME
    env["PYTHONUNBUFFERED"] = "1"

    log_path = os.path.abspath("blog_e2e_backend.log")
    log_file = open(log_path, "w", encoding="utf-8")

    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "blog_generator_backend:app", "--host", "127.0.0.1", "--port", "8010"],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    try:
        wait_for_blog_health(server, log_path)
        exercise_blog_api()
        time.sleep(4)
        verify_nexarch_backend(api_key, bearer)
    finally:
        revoke_api_key(bearer, api_key)
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        log_file.close()


if __name__ == "__main__":
    main()
