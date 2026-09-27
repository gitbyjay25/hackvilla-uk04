import os
import time
import uuid
from pathlib import Path

import pytest
import requests


BASE_URL = os.getenv("NEXARCH_TEST_BASE_URL", "http://127.0.0.1:8013").rstrip("/")
LOCAL_REPO_PATH = os.getenv(
    "NEXARCH_TEST_LOCAL_REPO_PATH",
    str((Path(__file__).resolve().parents[1] / "api").resolve()),
)


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _ensure_live_api_available() -> None:
    # This test targets a running API service rather than in-process ASGI.
    health_endpoints = ["/health", "/api/v1/health"]
    for endpoint in health_endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            if response.status_code < 500:
                return
        except requests.RequestException:
            continue
    pytest.skip(f"Live API is not reachable at {BASE_URL}")


@pytest.mark.integration
def test_system_architecture_alpha_code_flow_live_api() -> None:
    _ensure_live_api_available()
    session = requests.Session()

    email = f"sysarch_{uuid.uuid4().hex[:8]}@nex.dev"
    password = "TestPass123!"

    signup = session.post(
        f"{BASE_URL}/auth/signup",
        json={"email": email, "password": password, "full_name": "Sys Arch"},
        timeout=60,
    )
    assert signup.status_code == 200, signup.text
    token = signup.json().get("access_token")
    assert token

    headers = _auth_headers(token)

    install_url = session.get(
        f"{BASE_URL}/api/v1/system-architecture/github/install-url",
        headers=headers,
        timeout=60,
    )
    assert install_url.status_code == 200, install_url.text

    connect = session.post(
        f"{BASE_URL}/api/v1/system-architecture/repositories/connect",
        headers=headers,
        json={
            "owner": "local",
            "repo_name": f"Nexarch-Server-API-{uuid.uuid4().hex[:6]}",
            "default_branch": "main",
            "is_private": True,
            "is_monorepo": True,
            "local_repo_path": LOCAL_REPO_PATH,
        },
        timeout=120,
    )
    assert connect.status_code == 200, connect.text
    repository_id = connect.json().get("repository_id")
    assert repository_id

    snapshot = session.post(
        f"{BASE_URL}/api/v1/system-architecture/repositories/{repository_id}/snapshot",
        headers=headers,
        json={"use_default_branch": True},
        timeout=180,
    )
    assert snapshot.status_code == 200, snapshot.text
    snapshot_id = snapshot.json().get("snapshot_id")
    assert snapshot_id

    analyze = session.post(
        f"{BASE_URL}/api/v1/system-architecture/repositories/{repository_id}/analyze",
        headers=headers,
        json={
            "snapshot_id": snapshot_id,
            "mode": "sync",
            "cost_weight": 30,
            "scalability_weight": 35,
            "performance_weight": 35,
        },
        timeout=240,
    )
    assert analyze.status_code == 200, analyze.text
    variant_ids = analyze.json().get("variant_ids", [])
    assert len(variant_ids) >= 1

    variant_id = variant_ids[0]
    plan = session.post(
        f"{BASE_URL}/api/v1/alpha-code/plan-deeply",
        headers=headers,
        json={"architecture_variant_id": variant_id},
        timeout=120,
    )
    assert plan.status_code == 200, plan.text
    deep_plan_report_id = plan.json().get("deep_plan_report_id")
    assert deep_plan_report_id

    run = session.post(
        f"{BASE_URL}/api/v1/alpha-code/runs",
        headers=headers,
        json={
            "architecture_variant_id": variant_id,
            "deep_plan_report_id": deep_plan_report_id,
        },
        timeout=120,
    )
    assert run.status_code == 200, run.text
    run_id = run.json().get("run_id")
    assert run_id

    terminal_status = None
    for _ in range(20):
        time.sleep(3)
        status_resp = session.get(
            f"{BASE_URL}/api/v1/alpha-code/runs/{run_id}",
            headers=headers,
            timeout=60,
        )
        assert status_resp.status_code == 200, status_resp.text
        terminal_status = status_resp.json().get("status")
        if terminal_status in {"completed", "failed"}:
            break

    assert terminal_status == "completed", f"Unexpected terminal status: {terminal_status}"

    download = session.get(
        f"{BASE_URL}/api/v1/alpha-code/runs/{run_id}/download",
        headers=headers,
        timeout=120,
    )
    assert download.status_code == 200, download.text
    assert len(download.content) > 0
