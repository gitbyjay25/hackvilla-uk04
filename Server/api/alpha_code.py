from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import importlib
import difflib
import uuid
import zipfile
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.ai_client import get_ai_client
from core.config import get_settings
from db.base import SessionLocal, get_db
from db.models import (
    AlphaCodeRun,
    AlphaSandboxExecution,
    AlphaSandboxSession,
    ArchitectureDocument,
    ArchitectureVariant,
    ConnectedRepository,
    DeepPlanReport,
    RepoSnapshot,
    User,
)
from dependencies.auth import get_tenant_id_from_jwt
from services.notification_service import NotificationService


router = APIRouter(prefix="/api/v1/alpha-code", tags=["alpha-code"])
settings = get_settings()


def _load_alpha_pipeline_class():
    module = importlib.import_module("reasoning.alpha_codegen_pipeline")
    return getattr(module, "AlphaCodegenPipeline")


class PlanDeeplyRequest(BaseModel):
    architecture_variant_id: str


class StartAlphaCodeRequest(BaseModel):
    architecture_variant_id: str
    deep_plan_report_id: str


class CreateSandboxSessionRequest(BaseModel):
    alpha_run_id: str


class SandboxCommandRequest(BaseModel):
    command: str
    timeout_seconds: Optional[int] = None


class SandboxTestRunRequest(BaseModel):
    mode: str = "all"  # auto|uploaded|all
    custom_command: Optional[str] = None
    timeout_seconds: Optional[int] = None


class SandboxAutofixRequest(BaseModel):
    mode: str = "all"
    max_attempts: Optional[int] = None


class SandboxAutoValidationRequest(BaseModel):
    max_attempts: Optional[int] = None


def _workspace_root() -> Path:
    root = Path(settings.REPO_WORKSPACE_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _build_workflow_reference(variant_data: Dict[str, Any]) -> Dict[str, Any]:
    dependency_versions = variant_data.get("dependency_versions_used") or []
    benefits = variant_data.get("benefits_to_use") or []
    monthly_cost_estimate = variant_data.get("monthly_cost_estimate") or {}

    return {
        "dependencies": dependency_versions,
        "benefits": benefits,
        "monthly_cost_estimate": monthly_cost_estimate,
        "lowest_cost_per_month_usd": variant_data.get("lowest_cost_per_month_usd")
        or monthly_cost_estimate.get("lowest_cost_per_month_usd"),
    }


def _write_deep_plan(
    tenant_id: str,
    variant: ArchitectureVariant,
    repository: ConnectedRepository,
    snapshot: RepoSnapshot,
) -> Dict[str, str]:
    plan_id = str(uuid.uuid4())
    plan_root = _workspace_root() / tenant_id / repository.id / "deep_plan"
    plan_root.mkdir(parents=True, exist_ok=True)

    md_path = plan_root / f"deep_plan_{plan_id}.md"
    json_path = plan_root / f"deep_plan_{plan_id}.json"

    variant_data = json.loads(variant.variant_json)
    workflow_reference = _build_workflow_reference(variant_data)

    md_content = "\n".join(
        [
            f"# Deep Plan {plan_id}",
            "",
            f"Repository: {repository.full_name}",
            f"Snapshot: {snapshot.id}",
            f"Variant: {variant.title}",
            "",
            "## Current vs Target",
            "- Current architecture baseline from architecture document",
            "- Target architecture from selected variant",
            "",
            "## Dependency and Library Changes",
            "- Review dependency files and upgrade path",
            "- Add/replace runtime components based on variant priorities",
            "",
            "## Folder/File Refactor Strategy",
            "- Preserve project boundaries for monorepo packages",
            "- Apply incremental code transformations by service domain",
            "",
            "## Test and Validation Strategy",
            "- Run tests after transformation",
            "- Capture failures in structured logs",
            "",
            "## Rollback Strategy",
            "- Keep immutable snapshot",
            "- Generate full zip artifact for deterministic review",
            "",
            "## Major Changes",
            *[f"- {item}" for item in variant_data.get("major_changes", [])],
            "",
            "## Workflow Dependency Versions",
            *([
                f"- {item.get('name')} {item.get('version')} (source={item.get('source')})"
                for item in workflow_reference.get("dependencies", [])
            ] or ["- No dependency version mapping available"]),
            "",
            "## Workflow Benefits",
            *([f"- {item}" for item in workflow_reference.get("benefits", [])] or ["- No workflow benefits computed"]),
            "",
            "## Lowest Monthly Cost (Central India, USD)",
            f"- minimum_usd_per_month: {workflow_reference.get('lowest_cost_per_month_usd')}",
            f"- pricing_model: {(workflow_reference.get('monthly_cost_estimate') or {}).get('pricing_model')}",
            f"- reasoning_engine: {(workflow_reference.get('monthly_cost_estimate') or {}).get('reasoning_engine')}",
            f"- estimate_confidence: {(workflow_reference.get('monthly_cost_estimate') or {}).get('estimate_confidence')}",
            *([
                f"- {item.get('component')}: ${item.get('monthly_usd')}"
                for item in (workflow_reference.get("monthly_cost_estimate", {}).get("components") or [])
            ] or ["- No monthly cost component breakdown available"]),
            "",
            "## Pricing Assumptions",
            *([f"- {item}" for item in (workflow_reference.get("monthly_cost_estimate", {}).get("assumptions") or [])] or ["- No pricing assumptions captured"]),
            "",
            "## Pricing References",
            *([
                f"- {item.get('source')}: {item.get('evidence')}"
                for item in (workflow_reference.get("monthly_cost_estimate", {}).get("references") or [])
            ] or ["- No pricing references captured"]),
        ]
    )

    json_content = {
        "plan_id": plan_id,
        "tenant_id": tenant_id,
        "repository_id": repository.id,
        "snapshot_id": snapshot.id,
        "architecture_variant_id": variant.id,
        "variant_title": variant.title,
        "generated_at": datetime.utcnow().isoformat(),
        "sections": {
            "target_profile": variant_data.get("target_profile"),
            "major_changes": variant_data.get("major_changes", []),
            "workflow_reference": workflow_reference,
            "checks": ["tests", "build", "artifact_manifest"],
        },
    }

    md_path.write_text(md_content, encoding="utf-8")
    json_path.write_text(json.dumps(json_content, indent=2), encoding="utf-8")

    return {
        "plan_id": plan_id,
        "markdown_path": str(md_path),
        "json_path": str(json_path),
    }


def _zip_directory(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    zip_path = zip_path.resolve()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved == zip_path:
                continue
            zf.write(path, arcname=str(path.relative_to(source_dir)))


def _collect_file_inventory(root: Path) -> List[Dict[str, Any]]:
    """Collect exhaustive inventory for copied files in alpha workspace."""
    entries: List[Dict[str, Any]] = []
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".next", "dist", "build", "__pycache__"}]
        for name in files:
            path = Path(current) / name
            try:
                stat = path.stat()
                entries.append(
                    {
                        "path": str(path.relative_to(root)),
                        "size_bytes": stat.st_size,
                        "modified_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat(),
                    }
                )
            except OSError:
                continue
    entries.sort(key=lambda row: row["path"])
    return entries


def _estimate_alpha_execution_seconds(snapshot: RepoSnapshot, variant_data: Dict[str, Any], deep_plan: DeepPlanReport) -> float:
    """Estimate run time using mixed complexity signals, not size-only."""
    snapshot_mb = float(snapshot.snapshot_size_bytes or 0) / (1024.0 * 1024.0)
    major_changes = float(len(variant_data.get("major_changes", []) or []))
    try:
        deep_plan_size = float(Path(deep_plan.markdown_path).stat().st_size)
    except Exception:
        deep_plan_size = 0.0
    estimate = 2.0 + (snapshot_mb / 10.0) + (major_changes * 1.5) + (deep_plan_size / 8000.0)
    return max(1.0, round(estimate, 2))


def _resolve_alpha_mode(estimated_seconds: float) -> str:
    target = max(1, int(settings.SYSTEM_ARCH_SYNC_TARGET_SECONDS))
    return "sync" if estimated_seconds <= target else "async"


_SANDBOX_ACTIVE_STATUSES = {"starting", "running"}
_SANDBOX_RUNTIME_BACKENDS = {"local", "acr"}
_ACR_LOGGED_IN_REGISTRIES: set[str] = set()
_ACR_READY_IMAGES: set[str] = set()
_SANDBOX_FASTAPI_SMOKE_SCRIPT = "_nexarch_fastapi_smoke_runner.py"
_SANDBOX_FASTAPI_SMOKE_SCRIPT_LEGACY = ".nexarch_fastapi_smoke_test.py"


def _sandbox_idle_timeout_delta() -> timedelta:
    minutes = max(1, int(settings.ALPHA_SANDBOX_IDLE_TIMEOUT_MINUTES))
    return timedelta(minutes=minutes)


def _sandbox_max_active_sessions() -> int:
    return max(1, int(settings.ALPHA_SANDBOX_MAX_CONCURRENT_PER_USER))


def _sandbox_runtime_backend() -> str:
    backend = (settings.ALPHA_SANDBOX_RUNTIME_BACKEND or "local").strip().lower()
    if backend not in _SANDBOX_RUNTIME_BACKENDS:
        return "local"
    return backend


def _sandbox_runtime_metadata() -> Dict[str, Any]:
    backend = _sandbox_runtime_backend()
    return {
        "backend": backend,
        "acr_configured": bool(settings.has_acr_sandbox_config()),
        "acr_image": settings.ALPHA_SANDBOX_ACR_IMAGE if backend == "acr" else None,
        "acr_pull_policy": settings.ALPHA_SANDBOX_ACR_IMAGE_PULL_POLICY if backend == "acr" else None,
    }


def _truncate_text(value: str, max_chars: int = 50000) -> str:
    text = value or ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def _sandbox_root(tenant_id: str, repository_id: str) -> Path:
    root = _workspace_root() / tenant_id / repository_id / "sandbox_persistent"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _detect_stack_type(workspace: Path) -> str:
    if (workspace / "package.json").exists():
        return "node"
    if (workspace / "go.mod").exists():
        return "go"
    if (workspace / "pom.xml").exists() or (workspace / "build.gradle").exists() or (workspace / "build.gradle.kts").exists():
        return "java"
    if _workspace_has_fastapi_signals(workspace):
        return "fastapi"
    if (workspace / "requirements.txt").exists() or (workspace / "pyproject.toml").exists() or (workspace / "pytest.ini").exists():
        return "python"
    return "unknown"


def _serialize_sandbox_session(row: AlphaSandboxSession) -> Dict[str, Any]:
    return {
        "session_id": row.id,
        "alpha_run_id": row.alpha_run_id,
        "repository_id": row.repository_id,
        "runtime_backend": _sandbox_runtime_backend(),
        "workspace_path": row.workspace_path,
        "uploaded_tests_path": row.uploaded_tests_path,
        "persistent_root": row.persistent_root,
        "stack_type": row.stack_type,
        "status": row.status,
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "stopped_at": row.stopped_at.isoformat() if row.stopped_at else None,
        "last_activity_at": row.last_activity_at.isoformat() if row.last_activity_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_sandbox_execution(row: AlphaSandboxExecution) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    if row.metadata_json:
        try:
            meta = json.loads(row.metadata_json)
        except Exception:
            meta = {"raw": row.metadata_json}

    return {
        "execution_id": row.id,
        "session_id": row.session_id,
        "action_type": row.action_type,
        "command_text": row.command_text,
        "status": row.status,
        "exit_code": row.exit_code,
        "stdout": row.stdout_text or "",
        "stderr": row.stderr_text or "",
        "metadata": meta,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def _count_active_sandbox_sessions(db: Session, tenant_id: str) -> int:
    return (
        db.query(AlphaSandboxSession)
        .filter(
            AlphaSandboxSession.tenant_id == tenant_id,
            AlphaSandboxSession.status.in_(list(_SANDBOX_ACTIVE_STATUSES)),
        )
        .count()
    )


def _get_active_user_email(db: Session, tenant_id: str) -> Optional[str]:
    user = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.is_active == True)
        .order_by(User.created_at.asc())
        .first()
    )
    if not user or not user.email:
        return None
    return str(user.email).strip()


def _notify_sandbox_validation_status(
    db: Session,
    row: AlphaSandboxSession,
    passed: bool,
    attempts_count: int,
) -> Dict[str, Any]:
    smtp = NotificationService.get_smtp_runtime_status()
    recipient = _get_active_user_email(db, row.tenant_id)

    payload = {
        "attempted": False,
        "configured": bool(smtp.get("configured", False)),
        "recipient": recipient,
        "disabled_reason": smtp.get("disabled_reason"),
    }

    if not recipient:
        payload["reason"] = "no-recipient"
        return payload

    if not payload["configured"] or payload["disabled_reason"]:
        payload["reason"] = "smtp-not-configured"
        return payload

    NotificationService.send_alpha_code_status(
        to_email=recipient,
        run_id=row.alpha_run_id,
        status="completed" if passed else "failed",
        summary=(
            f"Sandbox automatic validation {'passed' if passed else 'finished without pass'} "
            f"after {attempts_count} attempt(s)."
        ),
    )
    payload["attempted"] = True
    payload["reason"] = None
    return payload


def _expire_if_idle(db: Session, row: AlphaSandboxSession) -> None:
    if row.status not in _SANDBOX_ACTIVE_STATUSES:
        return
    now = datetime.utcnow()
    if row.expires_at and row.expires_at < now:
        row.status = "stopped"
        row.stopped_at = now
        row.error_message = "Session stopped due to idle timeout"
        db.commit()
        db.refresh(row)


def _touch_session(db: Session, row: AlphaSandboxSession) -> None:
    now = datetime.utcnow()
    row.last_activity_at = now
    row.expires_at = now + _sandbox_idle_timeout_delta()
    db.commit()
    db.refresh(row)


def _get_sandbox_session_or_404(db: Session, tenant_id: str, session_id: str) -> AlphaSandboxSession:
    row = (
        db.query(AlphaSandboxSession)
        .filter(AlphaSandboxSession.id == session_id, AlphaSandboxSession.tenant_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Sandbox session not found")
    _expire_if_idle(db, row)
    return row


def _ensure_running_session(db: Session, row: AlphaSandboxSession) -> None:
    _expire_if_idle(db, row)
    if row.status != "running":
        raise HTTPException(status_code=400, detail="Sandbox session is not running")


def _normalize_acr_pull_policy(raw: str) -> str:
    value = (raw or "if_not_present").strip().lower()
    if value not in {"always", "if_not_present"}:
        return "if_not_present"
    return value


def _build_acr_image_reference() -> str:
    image = (settings.ALPHA_SANDBOX_ACR_IMAGE or "").strip()
    login_server = (settings.ALPHA_SANDBOX_ACR_LOGIN_SERVER or "").strip()
    if not image:
        return ""

    first_segment = image.split("/", 1)[0]
    has_explicit_registry = "." in first_segment or ":" in first_segment or first_segment == "localhost"
    if has_explicit_registry:
        return image
    if login_server:
        return f"{login_server}/{image}"
    return image


def _run_subprocess_command(
    args: Sequence[str],
    cwd: Optional[Path],
    timeout_seconds: int,
    stdin_text: Optional[str] = None,
) -> Dict[str, Any]:
    timeout = max(5, int(timeout_seconds or settings.ALPHA_SANDBOX_COMMAND_TIMEOUT_SECONDS))
    try:
        result = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin_text,
        )
        return {
            "exit_code": result.returncode,
            "stdout": _truncate_text(result.stdout or ""),
            "stderr": _truncate_text(result.stderr or ""),
            "timed_out": False,
        }
    except FileNotFoundError as exc:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": _truncate_text(str(exc)),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "exit_code": -1,
            "stdout": _truncate_text(stdout),
            "stderr": _truncate_text((stderr or "") + f"\nCommand timed out after {timeout}s"),
            "timed_out": True,
        }


def _ensure_acr_runtime_ready(timeout_seconds: int = 120) -> Dict[str, Any]:
    if _sandbox_runtime_backend() != "acr":
        return {"ok": True, "backend": "local"}

    if not settings.has_acr_sandbox_config():
        return {
            "ok": False,
            "error": "ACR runtime backend selected but ACR configuration is incomplete",
        }

    docker_probe = _run_subprocess_command(
        args=["docker", "version"],
        cwd=None,
        timeout_seconds=timeout_seconds,
    )
    if int(docker_probe.get("exit_code", 1)) != 0:
        return {
            "ok": False,
            "error": "Docker daemon is unavailable. Ensure Docker is installed and running.",
            "details": docker_probe.get("stderr") or docker_probe.get("stdout") or "",
        }

    login_server = settings.ALPHA_SANDBOX_ACR_LOGIN_SERVER.strip()
    if login_server not in _ACR_LOGGED_IN_REGISTRIES:
        login_result = _run_subprocess_command(
            args=[
                "docker",
                "login",
                login_server,
                "--username",
                settings.ALPHA_SANDBOX_ACR_USERNAME.strip(),
                "--password-stdin",
            ],
            cwd=None,
            timeout_seconds=timeout_seconds,
            stdin_text=settings.ALPHA_SANDBOX_ACR_PASSWORD,
        )
        if int(login_result.get("exit_code", 1)) != 0:
            return {
                "ok": False,
                "error": "ACR login failed for sandbox runtime",
                "details": login_result.get("stderr") or login_result.get("stdout") or "",
            }
        _ACR_LOGGED_IN_REGISTRIES.add(login_server)

    image_ref = _build_acr_image_reference()
    pull_policy = _normalize_acr_pull_policy(settings.ALPHA_SANDBOX_ACR_IMAGE_PULL_POLICY)
    needs_pull = pull_policy == "always"
    if not needs_pull and image_ref not in _ACR_READY_IMAGES:
        inspect_result = _run_subprocess_command(
            args=["docker", "image", "inspect", image_ref],
            cwd=None,
            timeout_seconds=timeout_seconds,
        )
        needs_pull = int(inspect_result.get("exit_code", 1)) != 0

    if needs_pull:
        pull_result = _run_subprocess_command(
            args=["docker", "pull", image_ref],
            cwd=None,
            timeout_seconds=max(timeout_seconds, 300),
        )
        if int(pull_result.get("exit_code", 1)) != 0:
            return {
                "ok": False,
                "error": "Failed to pull sandbox image from ACR",
                "details": pull_result.get("stderr") or pull_result.get("stdout") or "",
            }
    _ACR_READY_IMAGES.add(image_ref)

    return {
        "ok": True,
        "backend": "acr",
        "image": image_ref,
        "pull_policy": pull_policy,
    }


def _run_sandbox_runtime_command(
    command: str,
    cwd: Path,
    timeout_seconds: int,
    session: Optional[AlphaSandboxSession] = None,
) -> Dict[str, Any]:
    backend = _sandbox_runtime_backend()
    if backend != "acr":
        return _run_shell_command(command=command, cwd=cwd, timeout_seconds=timeout_seconds)

    ready = _ensure_acr_runtime_ready(timeout_seconds=max(120, timeout_seconds))
    if not ready.get("ok"):
        details = (ready.get("details") or "").strip()
        message = str(ready.get("error") or "Sandbox runtime is not ready")
        if details:
            message = f"{message}\n{details}"
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": _truncate_text(message),
            "timed_out": False,
        }

    image_ref = str(ready.get("image") or "").strip()
    docker_args: List[str] = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{cwd.resolve()}:/workspace",
        "--workdir",
        "/workspace",
    ]

    if session and session.uploaded_tests_path:
        uploaded_tests = Path(session.uploaded_tests_path)
        if uploaded_tests.exists():
            docker_args.extend(["-v", f"{uploaded_tests.resolve()}:/uploaded_tests"])

    docker_args.extend([image_ref, "/bin/sh", "-lc", command])
    return _run_subprocess_command(
        args=docker_args,
        cwd=None,
        timeout_seconds=timeout_seconds,
    )


def _run_shell_command(command: str, cwd: Path, timeout_seconds: int) -> Dict[str, Any]:
    timeout = max(5, int(timeout_seconds or settings.ALPHA_SANDBOX_COMMAND_TIMEOUT_SECONDS))
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "exit_code": result.returncode,
            "stdout": _truncate_text(result.stdout or ""),
            "stderr": _truncate_text(result.stderr or ""),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "exit_code": -1,
            "stdout": _truncate_text(stdout),
            "stderr": _truncate_text((stderr or "") + f"\nCommand timed out after {timeout}s"),
            "timed_out": True,
        }


def _record_sandbox_execution(
    db: Session,
    tenant_id: str,
    session_id: str,
    action_type: str,
    command_text: Optional[str],
    result: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> AlphaSandboxExecution:
    row = AlphaSandboxExecution(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        session_id=session_id,
        action_type=action_type,
        command_text=command_text,
        status="failed" if int(result.get("exit_code", 0)) != 0 else "completed",
        stdout_text=result.get("stdout") or "",
        stderr_text=result.get("stderr") or "",
        exit_code=int(result.get("exit_code", 0)),
        metadata_json=json.dumps(metadata or {}),
        completed_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


_FASTAPI_ASGI_FILE_CANDIDATES = [
    "Server/main.py",
    "server/main.py",
    "app/main.py",
    "src/main.py",
    "main.py",
    "Server/app.py",
    "server/app.py",
    "app.py",
    "asgi.py",
    "server.py",
    "src/app.py",
    "src/asgi.py",
    "app/asgi.py",
]


def _safe_read_text(path: Path, max_bytes: int = 512000) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return handle.read(max_bytes)
    except Exception:
        return ""


def _extract_fastapi_app_attr(source_text: str) -> Optional[str]:
    if "FastAPI(" not in source_text:
        return None
    match = re.search(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*FastAPI\(", source_text, flags=re.MULTILINE)
    if match:
        return match.group(1)
    return "app"


def _module_name_from_file(workspace: Path, source_file: Path) -> Optional[str]:
    try:
        relative = source_file.resolve().relative_to(workspace.resolve())
    except Exception:
        return None

    if relative.suffix != ".py":
        return None

    if relative.name == "__init__.py":
        parts = relative.parts[:-1]
    else:
        parts = relative.with_suffix("").parts
    if not parts:
        return None
    return ".".join(parts)


def _cleanup_legacy_fastapi_smoke_script(workspace: Path) -> None:
    legacy_path = workspace / _SANDBOX_FASTAPI_SMOKE_SCRIPT_LEGACY
    if legacy_path.exists():
        try:
            legacy_path.unlink()
        except Exception:
            pass


def _workspace_has_fastapi_signals(workspace: Path) -> bool:
    dependency_files = [
        workspace / "requirements.txt",
        workspace / "pyproject.toml",
        workspace / "Pipfile",
        workspace / "setup.py",
        workspace / "Server" / "requirements.txt",
    ]
    for dep_file in dependency_files:
        text = _safe_read_text(dep_file, max_bytes=200000)
        if text and "fastapi" in text.lower():
            return True

    for candidate in _FASTAPI_ASGI_FILE_CANDIDATES:
        text = _safe_read_text(workspace / candidate, max_bytes=200000)
        if "FastAPI(" in text:
            return True
    return False


def _discover_fastapi_asgi_targets(workspace: Path, max_scan: int = 1200) -> List[str]:
    discovered: List[str] = []

    for candidate in _FASTAPI_ASGI_FILE_CANDIDATES:
        candidate_path = workspace / candidate
        if not candidate_path.exists() or candidate_path.suffix != ".py":
            continue
        source_text = _safe_read_text(candidate_path)
        app_attr = _extract_fastapi_app_attr(source_text)
        module_name = _module_name_from_file(workspace, candidate_path)
        if app_attr and module_name:
            discovered.append(f"{module_name}:{app_attr}")

    scanned = 0
    for py_file in workspace.rglob("*.py"):
        scanned += 1
        if scanned > max_scan:
            break
        path_text = str(py_file).replace("\\", "/")
        if any(skip in path_text for skip in ["/.git/", "/node_modules/", "/.venv/", "/venv/", "/dist/", "/build/", "/__pycache__/"]):
            continue
        source_text = _safe_read_text(py_file)
        app_attr = _extract_fastapi_app_attr(source_text)
        if not app_attr:
            continue
        module_name = _module_name_from_file(workspace, py_file)
        if module_name:
            discovered.append(f"{module_name}:{app_attr}")

    deduped: List[str] = []
    seen = set()
    for target in discovered:
        key = target.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)
    return deduped


def _infer_fastapi_asgi_target(workspace: Path) -> Optional[str]:
    discovered = _discover_fastapi_asgi_targets(workspace)
    if discovered:
        return discovered[0]

    for candidate in _FASTAPI_ASGI_FILE_CANDIDATES:
        candidate_path = workspace / candidate
        if not candidate_path.exists() or candidate_path.suffix != ".py":
            continue
        source_text = _safe_read_text(candidate_path)
        app_attr = _extract_fastapi_app_attr(source_text)
        module_name = _module_name_from_file(workspace, candidate_path)
        if app_attr and module_name:
            return f"{module_name}:{app_attr}"

    scanned = 0
    for py_file in workspace.rglob("*.py"):
        scanned += 1
        if scanned > 800:
            break
        path_text = str(py_file).replace("\\", "/")
        if any(skip in path_text for skip in ["/.git/", "/node_modules/", "/.venv/", "/venv/", "/dist/", "/build/", "/__pycache__/"]):
            continue
        source_text = _safe_read_text(py_file)
        app_attr = _extract_fastapi_app_attr(source_text)
        if not app_attr:
            continue
        module_name = _module_name_from_file(workspace, py_file)
        if module_name:
            return f"{module_name}:{app_attr}"
    return None


def _write_fastapi_smoke_script(workspace: Path, asgi_target: str) -> Path:
    _cleanup_legacy_fastapi_smoke_script(workspace)
    script_path = workspace / _SANDBOX_FASTAPI_SMOKE_SCRIPT
    script = f'''import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ASGI_TARGET = {json.dumps(asgi_target)}
HOST = "127.0.0.1"


def pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def http_get(path: str, timeout: float = 4.0):
    url = f"http://{{HOST}}:{{PORT}}{{path}}"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(8192).decode("utf-8", errors="ignore")
            return int(response.getcode()), body, None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(8192).decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        return int(exc.code), body, None
    except Exception as exc:
        return None, "", str(exc)


def terminate_process(process: subprocess.Popen) -> tuple[str, str]:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    try:
        stdout, stderr = process.communicate(timeout=5)
    except Exception:
        stdout, stderr = "", ""
    return stdout or "", stderr or ""


PORT = pick_port()
environment = os.environ.copy()
python_path = environment.get("PYTHONPATH", "")
extra_paths = os.pathsep.join([".", ".nexarch_python_deps"])
environment["PYTHONPATH"] = extra_paths + (os.pathsep + python_path if python_path else "")

module_name, app_name = (ASGI_TARGET.split(":", 1) + [""])[:2]
import_check = subprocess.run(
    [
        sys.executable,
        "-c",
        "import importlib,sys; m=importlib.import_module(sys.argv[1]); getattr(m, sys.argv[2])",
        module_name,
        app_name,
    ],
    capture_output=True,
    text=True,
    env=environment,
)

if import_check.returncode != 0:
    summary = {{
        "asgi_target": ASGI_TARGET,
        "host": HOST,
        "port": PORT,
        "startup_ready": False,
        "startup_error": "ASGI import check failed",
        "reachable_count": 0,
        "probe_results": [],
        "uvicorn_exit_code": None,
        "uvicorn_stdout_tail": "",
        "uvicorn_stderr_tail": "",
        "asgi_import_stdout_tail": (import_check.stdout or "")[-3000:],
        "asgi_import_stderr_tail": (import_check.stderr or "")[-3000:],
    }}
    print(json.dumps(summary, indent=2))
    raise SystemExit(1)

uvicorn_cmd = [
    sys.executable,
    "-m",
    "uvicorn",
    ASGI_TARGET,
    "--host",
    HOST,
    "--port",
    str(PORT),
    "--log-level",
    "warning",
    "--no-access-log",
]

process = subprocess.Popen(
    uvicorn_cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=environment,
)

startup_ready = False
startup_error = None
for _ in range(80):
    if process.poll() is not None:
        startup_error = "uvicorn exited before becoming ready"
        break
    status, _, error = http_get("/openapi.json", timeout=1.2)
    if status is not None or error is None:
        startup_ready = True
        break
    time.sleep(0.25)

results = []
reachable_count = 0
openapi_paths = []

if startup_ready:
    status, body, error = http_get("/openapi.json")
    if status == 200:
        try:
            payload = json.loads(body)
            paths = payload.get("paths") or {{}}
            for path_name, methods in paths.items():
                if "{{" in path_name or "}}" in path_name:
                    continue
                if not isinstance(methods, dict):
                    continue
                method_keys = {{str(key).upper() for key in methods.keys()}}
                if method_keys.intersection({{"GET", "HEAD", "OPTIONS"}}):
                    openapi_paths.append(path_name)
        except Exception:
            pass

    probes = ["/health", "/healthz", "/docs", "/openapi.json", "/"] + openapi_paths
    seen = set()
    for path in probes:
        if path in seen:
            continue
        seen.add(path)
        if len(results) >= 12:
            break
        status, _, error = http_get(path)
        reachable = status is not None and int(status) < 500
        if reachable:
            reachable_count += 1
        results.append({{
            "path": path,
            "status": status,
            "error": error,
            "reachable": reachable,
        }})

stdout_text, stderr_text = terminate_process(process)

summary = {{
    "asgi_target": ASGI_TARGET,
    "host": HOST,
    "port": PORT,
    "startup_ready": startup_ready,
    "startup_error": startup_error,
    "reachable_count": reachable_count,
    "probe_results": results,
    "uvicorn_exit_code": process.returncode,
    "uvicorn_stdout_tail": stdout_text[-3000:],
    "uvicorn_stderr_tail": stderr_text[-3000:],
}}
print(json.dumps(summary, indent=2))

if startup_ready and reachable_count > 0:
    raise SystemExit(0)
raise SystemExit(1)
'''
    script_path.write_text(script, encoding="utf-8")
    return script_path


def _build_fastapi_smoke_command(workspace: Path, runtime_backend: str, asgi_target: Optional[str] = None) -> Optional[str]:
    if not _workspace_has_fastapi_signals(workspace):
        return None
    selected_target = asgi_target or _infer_fastapi_asgi_target(workspace)
    if not selected_target:
        return None
    script_path = _write_fastapi_smoke_script(workspace, selected_target)
    if runtime_backend == "acr":
        return f"PYTHONPATH=.nexarch_python_deps:$PYTHONPATH python {script_path.name}"
    return f'"{sys.executable}" "{script_path.name}"'


def _has_nested_python_tests(workspace: Path) -> bool:
    scanned = 0
    for py_file in workspace.rglob("*.py"):
        scanned += 1
        if scanned > 1200:
            break
        file_name = py_file.name
        if file_name in {_SANDBOX_FASTAPI_SMOKE_SCRIPT, _SANDBOX_FASTAPI_SMOKE_SCRIPT_LEGACY}:
            continue
        if file_name.startswith(".nexarch_"):
            continue
        if file_name.startswith("test_") or file_name.endswith("_test.py"):
            path_text = str(py_file).replace("\\", "/")
            if any(skip in path_text for skip in ["/.git/", "/node_modules/", "/.venv/", "/venv/", "/dist/", "/build/", "/__pycache__/"]):
                continue
            return True
    return False


def _discover_auto_test_commands(workspace: Path, runtime_backend: str = "local") -> List[str]:
    commands: List[str] = []

    fastapi_smoke_command = _build_fastapi_smoke_command(workspace, runtime_backend=runtime_backend)
    if fastapi_smoke_command:
        commands.append(fastapi_smoke_command)

    has_pytest_config = (workspace / "pytest.ini").exists() or (workspace / "tox.ini").exists()
    has_python_tests = (workspace / "tests").exists() or bool(list(workspace.glob("test_*.py"))) or _has_nested_python_tests(workspace)
    if has_pytest_config or has_python_tests:
        ignore_current = f"--ignore={_SANDBOX_FASTAPI_SMOKE_SCRIPT}"
        ignore_legacy = f"--ignore={_SANDBOX_FASTAPI_SMOKE_SCRIPT_LEGACY}"
        if runtime_backend == "acr":
            commands.append(f"PYTHONPATH=.nexarch_python_deps:$PYTHONPATH python -m pytest -q {ignore_current} {ignore_legacy}")
        else:
            commands.append(f'"{sys.executable}" -m pytest -q {ignore_current} {ignore_legacy}')

    if (workspace / "package.json").exists():
        commands.append("npm test -- --watch=false")

    if (workspace / "go.mod").exists():
        commands.append("go test ./...")

    if (workspace / "pom.xml").exists():
        commands.append("mvn -q test")
    elif (workspace / "build.gradle").exists() or (workspace / "build.gradle.kts").exists():
        if (workspace / "gradlew.bat").exists():
            commands.append("gradlew.bat test")
        elif (workspace / "gradlew").exists():
            commands.append("./gradlew test")
        else:
            commands.append("gradle test")

    deduped: List[str] = []
    seen = set()
    for command in commands:
        key = command.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(command)
    return deduped


def _discover_uploaded_test_commands(uploaded_tests_path: Path, runtime_backend: str = "local") -> List[str]:
    if not uploaded_tests_path.exists():
        return []
    python_test_files = [
        p for p in uploaded_tests_path.rglob("*.py")
        if p.name.startswith("test_") or p.name.endswith("_test.py")
    ]
    if python_test_files:
        if runtime_backend == "acr":
            return ["PYTHONPATH=.nexarch_python_deps:$PYTHONPATH python -m pytest -q /uploaded_tests"]
        return [f'"{sys.executable}" -m pytest -q "{uploaded_tests_path}"']
    return []


def _build_test_command_set(
    workspace: Path,
    uploaded_tests_path: Path,
    mode: str,
    custom_command: Optional[str],
    runtime_backend: str = "local",
) -> List[str]:
    normalized_mode = (mode or "all").strip().lower()
    if custom_command and custom_command.strip():
        return [custom_command.strip()]

    auto_commands = _discover_auto_test_commands(workspace, runtime_backend=runtime_backend)
    uploaded_commands = _discover_uploaded_test_commands(uploaded_tests_path, runtime_backend=runtime_backend)

    if normalized_mode == "auto":
        commands = auto_commands
    elif normalized_mode == "uploaded":
        commands = uploaded_commands
    else:
        commands = auto_commands + uploaded_commands

    deduped: List[str] = []
    seen = set()
    for command in commands:
        key = command.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(command)
    return deduped


def _run_test_suite(
    workspace: Path,
    commands: List[str],
    timeout_seconds: int,
    session: Optional[AlphaSandboxSession] = None,
) -> Dict[str, Any]:
    command_results: List[Dict[str, Any]] = []
    for command in commands:
        result = _run_sandbox_runtime_command(
            command=command,
            cwd=workspace,
            timeout_seconds=timeout_seconds,
            session=session,
        )
        command_results.append({
            "command": command,
            "exit_code": result.get("exit_code"),
            "stdout": result.get("stdout") or "",
            "stderr": result.get("stderr") or "",
            "timed_out": bool(result.get("timed_out")),
        })

    success = bool(commands) and all(int(item.get("exit_code", 1)) == 0 for item in command_results)
    combined_stdout = "\n\n".join(item.get("stdout") or "" for item in command_results)
    combined_stderr = "\n\n".join(item.get("stderr") or "" for item in command_results)
    overall_exit_code = 0 if success else 1
    return {
        "success": success,
        "exit_code": overall_exit_code,
        "stdout": _truncate_text(combined_stdout),
        "stderr": _truncate_text(combined_stderr),
        "command_results": command_results,
        "commands_executed": commands,
    }


def _extract_installable_packages(test_output: str) -> Dict[str, List[str]]:
    python_packages = set(re.findall(r"No module named ['\"]([A-Za-z0-9_.-]+)['\"]", test_output or ""))
    python_packages.update(re.findall(r"ModuleNotFoundError:\s*No module named ['\"]([A-Za-z0-9_.-]+)['\"]", test_output or ""))
    node_packages = set(re.findall(r"Cannot find module ['\"]([A-Za-z0-9_@/.-]+)['\"]", test_output or ""))
    node_packages.update(re.findall(r"ERR_MODULE_NOT_FOUND.*['\"]([A-Za-z0-9_@/.-]+)['\"]", test_output or ""))

    def _safe_python_package(name: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_.-]+", name or ""))

    def _safe_node_package(name: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_@/.-]+", name or ""))

    return {
        "python": sorted([name for name in python_packages if _safe_python_package(name)]),
        "node": sorted([name for name in node_packages if _safe_node_package(name)]),
    }


def _attempt_dependency_fix(
    workspace: Path,
    combined_output: str,
    timeout_seconds: int,
    session: Optional[AlphaSandboxSession] = None,
) -> Dict[str, Any]:
    runtime_backend = _sandbox_runtime_backend()
    packages = _extract_installable_packages(combined_output)
    actions: List[Dict[str, Any]] = []

    for package_name in packages.get("python", []):
        if runtime_backend == "acr":
            command = f"python -m pip install --target .nexarch_python_deps {package_name}"
        else:
            command = f'"{sys.executable}" -m pip install {package_name}'
        result = _run_sandbox_runtime_command(
            command=command,
            cwd=workspace,
            timeout_seconds=timeout_seconds,
            session=session,
        )
        actions.append({
            "type": "pip_install",
            "package": package_name,
            "result": result,
        })

    if (workspace / "package.json").exists():
        for package_name in packages.get("node", []):
            command = f"npm install {package_name}"
            result = _run_sandbox_runtime_command(
                command=command,
                cwd=workspace,
                timeout_seconds=timeout_seconds,
                session=session,
            )
            actions.append({
                "type": "npm_install",
                "package": package_name,
                "result": result,
            })

    applied = bool(actions)
    all_success = applied and all(int(action.get("result", {}).get("exit_code", 1)) == 0 for action in actions)
    return {
        "applied": applied,
        "all_success": all_success,
        "actions": actions,
    }


def _build_pytest_auto_command(runtime_backend: str) -> str:
    ignore_current = f"--ignore={_SANDBOX_FASTAPI_SMOKE_SCRIPT}"
    ignore_legacy = f"--ignore={_SANDBOX_FASTAPI_SMOKE_SCRIPT_LEGACY}"
    if runtime_backend == "acr":
        return f"PYTHONPATH=.nexarch_python_deps:$PYTHONPATH python -m pytest -q {ignore_current} {ignore_legacy}"
    return f'"{sys.executable}" -m pytest -q {ignore_current} {ignore_legacy}'


def _build_structural_probe_command(runtime_backend: str) -> str:
    python_bin = "python" if runtime_backend == "acr" else f'"{sys.executable}"'
    probe_code = (
        "import pathlib,sys; "
        "files=[p for p in pathlib.Path('.').rglob('*') if p.is_file()]; "
        "py=[p for p in files if p.suffix=='.py']; "
        "print(f'files={len(files)} python_files={len(py)}'); "
        "sys.exit(0 if files else 1)"
    )
    return f'{python_bin} -c "{probe_code}"'


def _collect_langgraph_alpha_context(db: Session, row: AlphaSandboxSession) -> Dict[str, Any]:
    run = (
        db.query(AlphaCodeRun)
        .filter(AlphaCodeRun.id == row.alpha_run_id, AlphaCodeRun.tenant_id == row.tenant_id)
        .first()
    )
    variant = db.query(ArchitectureVariant).filter(ArchitectureVariant.id == run.architecture_variant_id).first() if run else None
    deep_plan = db.query(DeepPlanReport).filter(DeepPlanReport.id == run.deep_plan_report_id).first() if run else None

    summary_json = {}
    if run and run.summary_json:
        try:
            summary_json = json.loads(run.summary_json)
        except Exception:
            summary_json = {"raw": run.summary_json}

    deep_plan_excerpt = ""
    if deep_plan and deep_plan.markdown_path:
        try:
            deep_plan_excerpt = Path(deep_plan.markdown_path).read_text(encoding="utf-8")[:8000]
        except Exception:
            deep_plan_excerpt = ""

    reports_root = Path(run.workspace_path) / "reports" if run and run.workspace_path else None
    report_artifacts: Dict[str, str] = {}
    if reports_root and reports_root.exists():
        for name in [
            "platform_understanding.md",
            "system_design_architecture.md",
            "workflow_reference.md",
            "parallel_pipeline_report.json",
            "summary.json",
        ]:
            target = reports_root / name
            if target.exists():
                try:
                    report_artifacts[name] = target.read_text(encoding="utf-8")[:8000]
                except Exception:
                    report_artifacts[name] = ""

    variant_json = {}
    if variant and variant.variant_json:
        try:
            variant_json = json.loads(variant.variant_json)
        except Exception:
            variant_json = {"raw": variant.variant_json}

    return {
        "tenant_id": row.tenant_id,
        "alpha_run_id": row.alpha_run_id,
        "repository_id": row.repository_id,
        "variant_id": run.architecture_variant_id if run else None,
        "deep_plan_id": run.deep_plan_report_id if run else None,
        "variant": variant_json,
        "run_summary": summary_json,
        "deep_plan_excerpt": deep_plan_excerpt,
        "report_artifacts": report_artifacts,
    }


def _plan_sandbox_tests_with_langgraph(
    workspace: Path,
    runtime_backend: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    fallback_commands = _build_test_command_set(
        workspace=workspace,
        uploaded_tests_path=workspace / "uploaded_tests_placeholder",
        mode="auto",
        custom_command=None,
        runtime_backend=runtime_backend,
    )
    if not fallback_commands:
        fallback_commands = [_build_structural_probe_command(runtime_backend)]

    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return {
            "planning_engine": "heuristic_fallback",
            "commands": fallback_commands,
            "fix_strategies": [
                "dependency_install",
                "fastapi_asgi_target_rotation",
            ],
            "fastapi_targets": _discover_fastapi_asgi_targets(workspace),
            "selected_fastapi_target": _infer_fastapi_asgi_target(workspace),
            "context_digest": {
                "variant_id": context.get("variant_id"),
                "deep_plan_id": context.get("deep_plan_id"),
            },
        }

    class SandboxPlanningState(Dict[str, Any]):
        pass

    def inspect_workspace_node(state: SandboxPlanningState) -> SandboxPlanningState:
        has_pytest_config = (workspace / "pytest.ini").exists() or (workspace / "tox.ini").exists()
        has_python_tests = (workspace / "tests").exists() or bool(list(workspace.glob("test_*.py"))) or _has_nested_python_tests(workspace)

        package_json = workspace / "package.json"
        node_has_test_script = False
        if package_json.exists():
            try:
                package_payload = json.loads(package_json.read_text(encoding="utf-8"))
                node_has_test_script = bool((package_payload.get("scripts") or {}).get("test"))
            except Exception:
                node_has_test_script = False

        fastapi_targets = _discover_fastapi_asgi_targets(workspace)
        markers = {
            "has_pytest_config": has_pytest_config,
            "has_python_tests": has_python_tests,
            "has_package_json": package_json.exists(),
            "node_has_test_script": node_has_test_script,
            "has_go_mod": (workspace / "go.mod").exists(),
            "has_maven": (workspace / "pom.xml").exists(),
            "has_gradle": (workspace / "build.gradle").exists() or (workspace / "build.gradle.kts").exists(),
            "fastapi_targets": fastapi_targets,
        }
        return {"markers": markers}

    def summarize_context_node(state: SandboxPlanningState) -> SandboxPlanningState:
        variant = context.get("variant") or {}
        run_summary = context.get("run_summary") or {}
        digest = {
            "variant_id": context.get("variant_id"),
            "deep_plan_id": context.get("deep_plan_id"),
            "variant_title": variant.get("title") or run_summary.get("variant"),
            "major_change_count": len(variant.get("major_changes") or run_summary.get("major_changes") or []),
            "context_files": sorted(list((context.get("report_artifacts") or {}).keys())),
        }
        return {"context_digest": digest}

    def generate_plan_node(state: SandboxPlanningState) -> SandboxPlanningState:
        markers = state.get("markers") or {}
        commands: List[str] = []

        fastapi_targets = markers.get("fastapi_targets") or []
        selected_fastapi_target = fastapi_targets[0] if fastapi_targets else None
        if selected_fastapi_target:
            smoke_cmd = _build_fastapi_smoke_command(workspace, runtime_backend, asgi_target=selected_fastapi_target)
            if smoke_cmd:
                commands.append(smoke_cmd)

        if markers.get("has_pytest_config") or markers.get("has_python_tests"):
            commands.append(_build_pytest_auto_command(runtime_backend))

        if markers.get("node_has_test_script"):
            commands.append("npm test -- --watch=false")
        elif markers.get("has_package_json"):
            commands.append("npm run test --if-present")

        if markers.get("has_go_mod"):
            commands.append("go test ./...")
        if markers.get("has_maven"):
            commands.append("mvn -q test")
        if markers.get("has_gradle"):
            if (workspace / "gradlew.bat").exists():
                commands.append("gradlew.bat test")
            elif (workspace / "gradlew").exists():
                commands.append("./gradlew test")
            else:
                commands.append("gradle test")

        deduped: List[str] = []
        seen = set()
        for command in commands:
            key = command.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(command)

        if not deduped:
            deduped = [_build_structural_probe_command(runtime_backend)]

        return {
            "commands": deduped,
            "selected_fastapi_target": selected_fastapi_target,
        }

    def generate_fix_node(state: SandboxPlanningState) -> SandboxPlanningState:
        return {
            "fix_strategies": [
                {"name": "dependency_install", "description": "Install missing python/node modules inferred from test output"},
                {"name": "fastapi_asgi_target_rotation", "description": "Rotate ASGI module target when uvicorn startup/import fails"},
            ]
        }

    def finalize_node(state: SandboxPlanningState) -> SandboxPlanningState:
        return {
            "plan": {
                "planning_engine": "langgraph",
                "commands": state.get("commands") or fallback_commands,
                "fix_strategies": state.get("fix_strategies") or [],
                "fastapi_targets": (state.get("markers") or {}).get("fastapi_targets") or [],
                "selected_fastapi_target": state.get("selected_fastapi_target"),
                "context_digest": state.get("context_digest") or {},
            }
        }

    workflow = StateGraph(SandboxPlanningState)
    workflow.add_node("inspect_workspace", inspect_workspace_node)
    workflow.add_node("summarize_context", summarize_context_node)
    workflow.add_node("generate_plan", generate_plan_node)
    workflow.add_node("generate_fix", generate_fix_node)
    workflow.add_node("finalize", finalize_node)

    workflow.set_entry_point("inspect_workspace")
    workflow.add_edge("inspect_workspace", "summarize_context")
    workflow.add_edge("summarize_context", "generate_plan")
    workflow.add_edge("generate_plan", "generate_fix")
    workflow.add_edge("generate_fix", "finalize")
    workflow.add_edge("finalize", END)

    output = workflow.compile().invoke({})
    plan = output.get("plan") or {}
    if not plan.get("commands"):
        plan["commands"] = fallback_commands
    return plan


def _apply_auto_validation_fix(
    workspace: Path,
    runtime_backend: str,
    commands: List[str],
    current_fastapi_target: Optional[str],
    fastapi_targets: List[str],
    combined_output: str,
    timeout_seconds: int,
    session: Optional[AlphaSandboxSession] = None,
) -> Dict[str, Any]:
    updated_commands = list(commands)
    actions: List[Dict[str, Any]] = []
    applied = False

    dependency_fix = _attempt_dependency_fix(
        workspace=workspace,
        combined_output=combined_output,
        timeout_seconds=timeout_seconds,
        session=session,
    )
    if dependency_fix.get("applied"):
        actions.append(
            {
                "type": "dependency_install",
                "all_success": bool(dependency_fix.get("all_success")),
                "actions": dependency_fix.get("actions") or [],
            }
        )
        applied = True

    failure_markers = [
        "ASGI import check failed",
        "uvicorn exited before becoming ready",
        "ModuleNotFoundError",
        "ImportError",
    ]
    should_rotate_fastapi_target = any(marker in (combined_output or "") for marker in failure_markers)
    if should_rotate_fastapi_target and fastapi_targets:
        try:
            current_idx = fastapi_targets.index(current_fastapi_target) if current_fastapi_target in fastapi_targets else -1
        except ValueError:
            current_idx = -1

        if current_idx + 1 < len(fastapi_targets):
            next_target = fastapi_targets[current_idx + 1]
            next_smoke_command = _build_fastapi_smoke_command(
                workspace=workspace,
                runtime_backend=runtime_backend,
                asgi_target=next_target,
            )
            if next_smoke_command:
                updated_commands = [
                    command
                    for command in updated_commands
                    if _SANDBOX_FASTAPI_SMOKE_SCRIPT not in command and _SANDBOX_FASTAPI_SMOKE_SCRIPT_LEGACY not in command
                ]
                updated_commands.insert(0, next_smoke_command)
                actions.append(
                    {
                        "type": "fastapi_target_rotation",
                        "from": current_fastapi_target,
                        "to": next_target,
                    }
                )
                current_fastapi_target = next_target
                applied = True

    return {
        "applied": applied,
        "commands": updated_commands,
        "current_fastapi_target": current_fastapi_target,
        "actions": actions,
    }


def _run_langgraph_auto_validation(
    db: Session,
    row: AlphaSandboxSession,
    max_attempts: Optional[int] = None,
) -> Dict[str, Any]:
    workspace = Path(row.workspace_path)
    if not workspace.exists():
        raise HTTPException(status_code=400, detail="Sandbox workspace does not exist")

    configured_max = max(1, int(settings.ALPHA_SANDBOX_AUTOFIX_MAX_ATTEMPTS))
    attempts_limit = configured_max if max_attempts is None else max(1, min(configured_max, int(max_attempts)))
    timeout_seconds = int(settings.ALPHA_SANDBOX_COMMAND_TIMEOUT_SECONDS)
    runtime_backend = _sandbox_runtime_backend()

    context = _collect_langgraph_alpha_context(db=db, row=row)
    plan = _plan_sandbox_tests_with_langgraph(
        workspace=workspace,
        runtime_backend=runtime_backend,
        context=context,
    )

    commands = list(plan.get("commands") or [])
    if not commands:
        raise HTTPException(status_code=400, detail="No auto-test commands were generated for sandbox validation")

    fastapi_targets = list(plan.get("fastapi_targets") or [])
    current_fastapi_target = plan.get("selected_fastapi_target")

    attempts: List[Dict[str, Any]] = []
    passed = False
    last_test_result: Dict[str, Any] = {}

    for attempt_index in range(1, attempts_limit + 1):
        test_result = _run_test_suite(
            workspace=workspace,
            commands=commands,
            timeout_seconds=timeout_seconds,
            session=row,
        )
        last_test_result = test_result

        _record_sandbox_execution(
            db=db,
            tenant_id=row.tenant_id,
            session_id=row.id,
            action_type="auto_validation_test",
            command_text="\n".join(commands)[:4000],
            result={
                "exit_code": int(test_result.get("exit_code", 1)),
                "stdout": test_result.get("stdout") or "",
                "stderr": test_result.get("stderr") or "",
            },
            metadata={
                "attempt": attempt_index,
                "phase": "test",
                "commands": list(commands),
                "command_results": test_result.get("command_results", []),
            },
        )

        attempt_row: Dict[str, Any] = {
            "attempt": attempt_index,
            "commands": list(commands),
            "tests": {
                "success": bool(test_result.get("success")),
                "exit_code": test_result.get("exit_code"),
                "command_results": test_result.get("command_results", []),
            },
        }

        if test_result.get("success"):
            passed = True
            attempts.append(attempt_row)
            break

        combined_output = (test_result.get("stdout") or "") + "\n" + (test_result.get("stderr") or "")
        fix_cycle = _apply_auto_validation_fix(
            workspace=workspace,
            runtime_backend=runtime_backend,
            commands=commands,
            current_fastapi_target=current_fastapi_target,
            fastapi_targets=fastapi_targets,
            combined_output=combined_output,
            timeout_seconds=timeout_seconds,
            session=row,
        )
        attempt_row["fix_actions"] = fix_cycle.get("actions") or []

        _record_sandbox_execution(
            db=db,
            tenant_id=row.tenant_id,
            session_id=row.id,
            action_type="auto_validation_fix",
            command_text="auto_validation_fix",
            result={
                "exit_code": 0 if fix_cycle.get("applied") else 1,
                "stdout": json.dumps({"actions": fix_cycle.get("actions") or []}, indent=2),
                "stderr": "" if fix_cycle.get("applied") else "No applicable automated fix strategy found",
            },
            metadata={
                "attempt": attempt_index,
                "phase": "fix",
                "applied": bool(fix_cycle.get("applied")),
                "current_fastapi_target": current_fastapi_target,
            },
        )

        attempts.append(attempt_row)

        if not fix_cycle.get("applied"):
            break

        commands = list(fix_cycle.get("commands") or commands)
        current_fastapi_target = fix_cycle.get("current_fastapi_target")

    return {
        "planning_engine": plan.get("planning_engine") or "heuristic_fallback",
        "context_digest": plan.get("context_digest") or {},
        "generated_commands": plan.get("commands") or [],
        "final_commands": commands,
        "fastapi_targets": fastapi_targets,
        "selected_fastapi_target": plan.get("selected_fastapi_target"),
        "final_fastapi_target": current_fastapi_target,
        "fix_strategies": plan.get("fix_strategies") or [],
        "passed": passed,
        "attempts": attempts,
        "max_attempts": attempts_limit,
        "final_test_success": bool(last_test_result.get("success")),
        "final_exit_code": int(last_test_result.get("exit_code", 1)) if last_test_result else 1,
    }


def _validate_safe_relative_upload_path(path_value: str) -> Path:
    normalized = (path_value or "").replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        raise HTTPException(status_code=400, detail="Invalid upload path")
    return Path(*parts) if parts else Path("uploaded_tests")


def _prepare_sandbox_workspace_from_run(run: AlphaCodeRun, target_workspace: Path) -> None:
    source_workspace = Path(run.workspace_path) / "alpha_code"
    if not source_workspace.exists():
        raise HTTPException(status_code=400, detail="Alpha run workspace is unavailable")

    target_workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_workspace, target_workspace, dirs_exist_ok=True)


def _strip_markdown_code_fence(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return raw


def _safe_read_for_diff(path: Path, max_bytes: int = 500000) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return handle.read(max_bytes)
    except Exception:
        return ""


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _normalize_python_specifier(version: str) -> str:
    raw = str(version or "").strip()
    if not raw or raw.lower() == "unspecified":
        return ""
    if raw.startswith(("==", ">=", "<=", "~=", ">", "<", "!=")):
        return raw
    if raw.startswith(("^", "~")):
        raw = raw[1:].strip()
    if re.match(r"^\d+(?:\.\d+){0,3}", raw):
        return f"=={raw}"
    return ""


def _apply_requirements_transform(alpha_root: Path, dependencies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    requirements_path = alpha_root / "requirements.txt"
    if not requirements_path.exists():
        return actions

    existing_text = _safe_read_for_diff(requirements_path, max_bytes=300000)
    existing_names = {
        re.split(r"[<>=~!\[]", line.strip(), maxsplit=1)[0].strip().lower()
        for line in existing_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    additions: List[str] = []
    for dep in dependencies[:60]:
        name = str(dep.get("name") or "").strip().lower()
        if not name or name in existing_names or name.startswith("@") or "/" in name:
            continue
        if not re.fullmatch(r"[a-z0-9_.\-]+", name):
            continue
        spec = _normalize_python_specifier(str(dep.get("version") or ""))
        additions.append(f"{name}{spec}")
        existing_names.add(name)
        if len(additions) >= 12:
            break

    if not additions:
        return actions

    merged = existing_text.rstrip() + "\n\n# Added by Nexarch Alpha variant transform\n" + "\n".join(additions) + "\n"
    requirements_path.write_text(merged, encoding="utf-8")
    actions.append(
        {
            "type": "requirements_update",
            "path": "requirements.txt",
            "added": additions,
        }
    )
    return actions


def _normalize_node_version(version: str) -> str:
    raw = str(version or "").strip()
    if not raw or raw.lower() == "unspecified":
        return "latest"
    if raw.startswith(("^", "~", ">", "<", "=")):
        return raw
    if re.match(r"^\d+(?:\.\d+){0,3}", raw):
        return f"^{raw}"
    return "latest"


def _apply_package_json_transform(alpha_root: Path, dependencies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    package_path = alpha_root / "package.json"
    if not package_path.exists():
        return actions

    try:
        package_payload = json.loads(package_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return actions

    runtime_deps = package_payload.get("dependencies")
    if not isinstance(runtime_deps, dict):
        runtime_deps = {}
        package_payload["dependencies"] = runtime_deps

    added: Dict[str, str] = {}
    for dep in dependencies[:80]:
        name = str(dep.get("name") or "").strip()
        if not name or name in runtime_deps:
            continue
        if not re.fullmatch(r"[@A-Za-z0-9_./\-]+", name):
            continue
        runtime_deps[name] = _normalize_node_version(str(dep.get("version") or ""))
        added[name] = runtime_deps[name]
        if len(added) >= 12:
            break

    if not added:
        return actions

    package_path.write_text(json.dumps(package_payload, indent=2) + "\n", encoding="utf-8")
    actions.append(
        {
            "type": "package_json_update",
            "path": "package.json",
            "added": added,
        }
    )
    return actions


def _annotate_entrypoint_file(alpha_root: Path, variant_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    profile = str(variant_data.get("target_profile") or "balanced").lower()
    major_changes = [str(item).strip() for item in (variant_data.get("major_changes") or []) if str(item).strip()]

    candidates = [
        alpha_root / "main.py",
        alpha_root / "app.py",
        alpha_root / "server.py",
        alpha_root / "src" / "main.py",
        alpha_root / "src" / "app.py",
        alpha_root / "index.js",
        alpha_root / "app.js",
        alpha_root / "main.js",
        alpha_root / "src" / "index.js",
        alpha_root / "src" / "main.js",
    ]

    target_file = next((path for path in candidates if path.exists() and path.is_file()), None)
    if not target_file:
        return actions

    existing = target_file.read_text(encoding="utf-8", errors="ignore")
    if "NEXARCH_ALPHA_VARIANT" in existing:
        return actions

    ext = target_file.suffix.lower()
    summary = ", ".join(major_changes[:3]) if major_changes else "variant-aware structural updates"
    marker_line = f"NEXARCH_ALPHA_VARIANT profile={profile} changes={summary}"

    if ext == ".py":
        marker = f"# {marker_line}\n"
    elif ext in {".js", ".ts", ".tsx", ".jsx"}:
        marker = f"// {marker_line}\n"
    else:
        marker = f"/* {marker_line} */\n"

    target_file.write_text(marker + existing, encoding="utf-8")
    actions.append(
        {
            "type": "entrypoint_annotation",
            "path": str(target_file.relative_to(alpha_root)).replace("\\", "/"),
            "marker": marker_line,
        }
    )
    return actions


def _collect_ai_rewrite_candidates(alpha_root: Path, major_changes: List[str], limit: int = 4) -> List[Path]:
    stop_dirs = {".git", "node_modules", ".next", "dist", "build", "__pycache__", "venv", ".venv"}
    tokens = {
        token
        for change in major_changes
        for token in re.split(r"[^a-z0-9]+", change.lower())
        if len(token) >= 4
    }

    candidates: List[Dict[str, Any]] = []
    for current, dirs, files in os.walk(alpha_root):
        dirs[:] = [name for name in dirs if name not in stop_dirs]
        for file_name in files:
            path = Path(current) / file_name
            if path.suffix.lower() != ".py":
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > 90000:
                continue

            rel = str(path.relative_to(alpha_root)).replace("\\", "/")
            lower_rel = rel.lower()
            if any(part in lower_rel for part in ["/tests/", "test_", "_test.py", "/migrations/"]):
                continue

            score = 1
            if file_name in {"main.py", "app.py", "server.py", "config.py", "settings.py"}:
                score += 7
            if any(key in lower_rel for key in ["/api/", "/service", "/core/", "/src/"]):
                score += 3
            if any(token in lower_rel for token in tokens):
                score += 5

            candidates.append({"path": path, "score": score, "rel": rel})

    ranked = sorted(candidates, key=lambda item: (-item["score"], item["rel"]))
    return [item["path"] for item in ranked[:limit]]


def _ai_rewrite_python_file(
    file_path: Path,
    alpha_root: Path,
    variant_data: Dict[str, Any],
    deep_plan_text: str,
) -> Dict[str, Any]:
    client = get_ai_client()
    if not client.llm:
        return {"changed": False, "reason": "ai_not_configured"}

    existing = _safe_read_for_diff(file_path, max_bytes=120000)
    if not existing.strip():
        return {"changed": False, "reason": "empty_source"}

    relative_path = str(file_path.relative_to(alpha_root)).replace("\\", "/")
    major_changes = variant_data.get("major_changes") or []
    target_profile = variant_data.get("target_profile") or "balanced"

    prompt = (
        "You are upgrading code for an alpha architecture variant. "
        "Rewrite the Python file with concrete implementation changes that reflect the target profile and major changes. "
        "Keep valid Python syntax and preserve imports/behavior where possible. "
        "Return only full Python source code without markdown fences.\n\n"
        f"Target profile: {target_profile}\n"
        f"Major changes: {major_changes}\n"
        f"Deep plan excerpt: {(deep_plan_text or '')[:2200]}\n\n"
        f"File path: {relative_path}\n"
        "Current file:\n"
        f"{existing[:100000]}"
    )

    try:
        response = client.llm.invoke(prompt)
    except Exception as exc:
        return {"changed": False, "reason": f"ai_invoke_failed:{exc}"}

    content = getattr(response, "content", response)
    rewritten = _strip_markdown_code_fence(str(content))
    if not rewritten or rewritten.strip() == existing.strip():
        return {"changed": False, "reason": "no_change"}

    try:
        compile(rewritten, str(file_path), "exec")
    except Exception as exc:
        return {"changed": False, "reason": f"syntax_invalid:{exc}"}

    file_path.write_text(rewritten, encoding="utf-8")
    return {"changed": True, "reason": "ai_rewrite_applied"}


def _build_diff_report(
    snapshot_root: Path,
    alpha_root: Path,
    changed_paths: List[str],
) -> str:
    lines: List[str] = ["# Diff Report", "", "## Changed Files"]
    if not changed_paths:
        lines.append("- No file modifications were applied.")
        return "\n".join(lines) + "\n"

    for rel_path in changed_paths:
        lines.append(f"- {rel_path}")

    lines.extend(["", "## Unified Diffs", ""])
    for rel_path in changed_paths:
        before_path = snapshot_root / rel_path
        after_path = alpha_root / rel_path
        before_text = _safe_read_for_diff(before_path)
        after_text = _safe_read_for_diff(after_path)
        before_lines = before_text.splitlines()
        after_lines = after_text.splitlines()

        diff = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"snapshot/{rel_path}",
                tofile=f"alpha/{rel_path}",
                n=2,
                lineterm="",
            )
        )

        lines.append(f"### {rel_path}")
        if not diff:
            lines.append("No textual diff available.")
            lines.append("")
            continue

        lines.append("```diff")
        lines.extend(diff[:500])
        lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _apply_variant_transformations(
    alpha_root: Path,
    snapshot_root: Path,
    reports_root: Path,
    variant_data: Dict[str, Any],
    deep_plan_text: str,
) -> Dict[str, Any]:
    dependencies = list((variant_data or {}).get("dependency_versions_used") or [])
    major_changes = [str(item) for item in ((variant_data or {}).get("major_changes") or []) if str(item).strip()]

    actions: List[Dict[str, Any]] = []
    actions.extend(_apply_requirements_transform(alpha_root, dependencies))
    actions.extend(_apply_package_json_transform(alpha_root, dependencies))
    actions.extend(_annotate_entrypoint_file(alpha_root, variant_data))

    ai_attempts: List[Dict[str, Any]] = []
    if settings.ENABLE_AI_GENERATION:
        ai_candidates = _collect_ai_rewrite_candidates(alpha_root, major_changes, limit=4)
        for candidate in ai_candidates:
            rel = str(candidate.relative_to(alpha_root)).replace("\\", "/")
            before = _safe_read_for_diff(candidate)
            before_hash = _sha256_text(before)
            result = _ai_rewrite_python_file(
                file_path=candidate,
                alpha_root=alpha_root,
                variant_data=variant_data,
                deep_plan_text=deep_plan_text,
            )
            after = _safe_read_for_diff(candidate)
            after_hash = _sha256_text(after)
            ai_attempts.append(
                {
                    "path": rel,
                    "changed": bool(result.get("changed")),
                    "reason": result.get("reason"),
                }
            )
            if result.get("changed") and before_hash != after_hash:
                actions.append(
                    {
                        "type": "ai_rewrite",
                        "path": rel,
                        "reason": result.get("reason"),
                    }
                )

    if not actions:
        notes_path = alpha_root / "ALPHA_VARIANT_NOTES.md"
        notes_lines = [
            "# Alpha Variant Notes",
            "",
            f"- target_profile: {variant_data.get('target_profile')}",
            f"- major_changes: {major_changes}",
            "- note: No deterministic source-level rewrite candidate was auto-detected, so this variant guidance file was added.",
        ]
        notes_path.write_text("\n".join(notes_lines) + "\n", encoding="utf-8")
        actions.append(
            {
                "type": "variant_notes",
                "path": "ALPHA_VARIANT_NOTES.md",
                "reason": "fallback_mutation",
            }
        )

    changed_paths = sorted({str(action.get("path")) for action in actions if action.get("path")})
    diff_report = _build_diff_report(snapshot_root, alpha_root, changed_paths)
    (reports_root / "diff_report.md").write_text(diff_report, encoding="utf-8")

    changes_payload = {
        "applied_at": datetime.utcnow().isoformat(),
        "target_profile": variant_data.get("target_profile"),
        "major_changes": major_changes,
        "actions": actions,
        "ai_attempts": ai_attempts,
        "changed_files": changed_paths,
        "changed_files_count": len(changed_paths),
    }
    (reports_root / "changes_applied.json").write_text(json.dumps(changes_payload, indent=2), encoding="utf-8")
    return changes_payload


def _enforce_upload_limits(file_count: int, total_bytes: int) -> None:
    max_files = max(1, int(settings.ALPHA_SANDBOX_MAX_UPLOAD_FILES))
    max_total_bytes = max(1, int(settings.ALPHA_SANDBOX_MAX_UPLOAD_TOTAL_MB)) * 1024 * 1024

    if file_count > max_files:
        raise HTTPException(status_code=400, detail=f"Too many files. Max allowed is {max_files}")
    if total_bytes > max_total_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Upload exceeds total size limit of {settings.ALPHA_SANDBOX_MAX_UPLOAD_TOTAL_MB} MB",
        )


def _write_deep_context_docs(
    reports_root: Path,
    run: AlphaCodeRun,
    repository: ConnectedRepository,
    snapshot: RepoSnapshot,
    variant: ArchitectureVariant,
    deep_plan: DeepPlanReport,
    alpha_root: Path,
) -> Dict[str, Any]:
    """Write high-detail markdown artifacts so alpha generation context is never lost."""
    variant_data = json.loads(variant.variant_json)
    workflow_reference = _build_workflow_reference(variant_data)

    architecture_doc = None
    architecture_payload: Dict[str, Any] = {}
    graph_payload: Dict[str, Any] = {}
    try:
        architecture_doc = Path(deep_plan.markdown_path).resolve().parents[2] / "architecture_docs"
    except Exception:
        architecture_doc = None

    file_inventory = _collect_file_inventory(alpha_root)
    total_bytes = sum(row["size_bytes"] for row in file_inventory)

    if architecture_doc and architecture_doc.exists():
        pass

    inventory_md = [
        f"# Copied Files Inventory ({run.id})",
        "",
        f"- total_files: {len(file_inventory)}",
        f"- total_size_bytes: {total_bytes}",
        "",
        "## Files",
    ]
    for item in file_inventory:
        inventory_md.append(
            f"- {item['path']} | size={item['size_bytes']} | modified_at={item['modified_at']}"
        )
    (reports_root / "copied_files_inventory.md").write_text("\n".join(inventory_md), encoding="utf-8")

    deep_plan_text = ""
    try:
        deep_plan_text = Path(deep_plan.markdown_path).read_text(encoding="utf-8")
    except Exception:
        deep_plan_text = "Deep plan markdown unavailable"

    platform_md = [
        "# Platform Understanding",
        "",
        "## Objective",
        "- Build alpha code in isolated alpha workspace only.",
        "- Never modify immutable original snapshot.",
        "- Preserve full decision context for architecture and implementation.",
        "",
        "## Repository Context",
        f"- repository: {repository.full_name}",
        f"- repository_id: {repository.id}",
        f"- snapshot_id: {snapshot.id}",
        f"- snapshot_branch: {snapshot.branch}",
        f"- snapshot_commit_sha: {snapshot.commit_sha or 'unknown'}",
        "",
        "## Selected Variant",
        f"- architecture_variant_id: {variant.id}",
        f"- title: {variant.title}",
        f"- variant_index: {variant.variant_index}",
        f"- major_changes: {variant_data.get('major_changes', [])}",
        f"- lowest_cost_per_month_usd: {workflow_reference.get('lowest_cost_per_month_usd')}",
        "",
        "## Workflow Dependency Versions",
        *([
            f"- {item.get('name')} {item.get('version')} (source={item.get('source')}, scope={item.get('scope')})"
            for item in workflow_reference.get("dependencies", [])
        ] or ["- No dependency version mapping available"]),
        "",
        "## Workflow Benefits",
        *([f"- {item}" for item in workflow_reference.get("benefits", [])] or ["- No workflow benefits computed"]),
        "",
        "## Deep Plan",
        f"- deep_plan_report_id: {deep_plan.id}",
        f"- deep_plan_markdown_path: {deep_plan.markdown_path}",
        f"- deep_plan_json_path: {deep_plan.json_path}",
        "",
        "## Deep Plan Content",
        deep_plan_text,
        "",
        "## Copied Workspace Summary",
        f"- alpha_workspace_root: {alpha_root}",
        f"- copied_file_count: {len(file_inventory)}",
        f"- copied_total_size_bytes: {total_bytes}",
    ]
    (reports_root / "platform_understanding.md").write_text("\n".join(platform_md), encoding="utf-8")

    system_design_md = [
        "# System Design Architecture Context",
        "",
        "## Selected Variant Strategy",
        f"- target_profile: {variant_data.get('target_profile')}",
        f"- weights: {variant_data.get('weights')}",
        f"- lowest_cost_per_month_usd: {workflow_reference.get('lowest_cost_per_month_usd')}",
        "",
        "## Architecture Reasoning",
        "- The selected variant is transformed in isolation within alpha workspace.",
        "- Snapshot remains immutable and untouched.",
        "- Generated reports preserve complete lineage for audit and replay.",
        "",
        "## Workflow Cost Components",
        *([
            f"- {item.get('component')}: ${item.get('monthly_usd')}"
            for item in (workflow_reference.get("monthly_cost_estimate", {}).get("components") or [])
        ] or ["- No monthly cost component breakdown available"]),
        "",
        "## Pricing Assumptions",
        *([f"- {item}" for item in (workflow_reference.get("monthly_cost_estimate", {}).get("assumptions") or [])] or ["- No pricing assumptions captured"]),
        "",
        "## Pricing References",
        *([
            f"- {item.get('source')}: {item.get('evidence')}"
            for item in (workflow_reference.get("monthly_cost_estimate", {}).get("references") or [])
        ] or ["- No pricing references captured"]),
        "",
        "## 2D System Design Graph",
        "- JSON graph output is provided in architecture_2d_graph.json when source architecture graph exists.",
    ]
    (reports_root / "system_design_architecture.md").write_text("\n".join(system_design_md), encoding="utf-8")

    (reports_root / "workflow_reference.json").write_text(
        json.dumps(workflow_reference, indent=2),
        encoding="utf-8",
    )

    workflow_md = [
        "# Workflow Reference",
        "",
        "## Lowest Monthly Cost (Central India, USD)",
        f"- minimum_usd_per_month: {workflow_reference.get('lowest_cost_per_month_usd')}",
        f"- pricing_model: {(workflow_reference.get('monthly_cost_estimate') or {}).get('pricing_model')}",
        f"- reasoning_engine: {(workflow_reference.get('monthly_cost_estimate') or {}).get('reasoning_engine')}",
        f"- estimate_confidence: {(workflow_reference.get('monthly_cost_estimate') or {}).get('estimate_confidence')}",
        "",
        "## Dependency Versions",
        *([
            f"- {item.get('name')} {item.get('version')} (source={item.get('source')}, scope={item.get('scope')})"
            for item in workflow_reference.get("dependencies", [])
        ] or ["- No dependency version mapping available"]),
        "",
        "## Pricing Assumptions",
        *([f"- {item}" for item in (workflow_reference.get("monthly_cost_estimate", {}).get("assumptions") or [])] or ["- No pricing assumptions captured"]),
        "",
        "## Pricing References",
        *([
            f"- {item.get('source')}: {item.get('evidence')}"
            for item in (workflow_reference.get("monthly_cost_estimate", {}).get("references") or [])
        ] or ["- No pricing references captured"]),
        "",
        "## Benefits",
        *([f"- {item}" for item in workflow_reference.get("benefits", [])] or ["- No workflow benefits computed"]),
    ]
    (reports_root / "workflow_reference.md").write_text("\n".join(workflow_md), encoding="utf-8")

    try:
        doc_row = Path(deep_plan.json_path).read_text(encoding="utf-8")
        architecture_payload = json.loads(doc_row)
    except Exception:
        architecture_payload = {}

    repo_root = Path(snapshot.snapshot_path).resolve().parents[1]
    graph_candidates = list((repo_root / "architecture_docs").glob("architecture_graph_*.json"))
    if graph_candidates:
        try:
            graph_payload = json.loads(graph_candidates[-1].read_text(encoding="utf-8"))
            (reports_root / "architecture_2d_graph.json").write_text(
                json.dumps(graph_payload, indent=2),
                encoding="utf-8",
            )
        except Exception:
            graph_payload = {}

    return {
        "file_inventory_count": len(file_inventory),
        "copied_total_size_bytes": total_bytes,
        "architecture_graph_available": bool(graph_payload),
        "workflow_reference_available": True,
        "architecture_payload": architecture_payload,
        "workflow_reference": workflow_reference,
    }


def _execute_alpha_run(db_factory, run_id: str) -> None:
    db = db_factory()
    try:
        run = db.query(AlphaCodeRun).filter(AlphaCodeRun.id == run_id).first()
        if not run:
            return

        run.status = "in_progress"
        run.started_at = datetime.utcnow()
        db.commit()

        snapshot = db.query(RepoSnapshot).filter(RepoSnapshot.id == run.snapshot_id).first()
        variant = db.query(ArchitectureVariant).filter(ArchitectureVariant.id == run.architecture_variant_id).first()
        deep_plan = db.query(DeepPlanReport).filter(DeepPlanReport.id == run.deep_plan_report_id).first()

        if not snapshot or not variant or not deep_plan:
            run.status = "failed"
            run.error_message = "Missing snapshot, variant, or deep plan"
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        workspace = Path(run.workspace_path)
        alpha_root = workspace / "alpha_code"
        reports_root = workspace / "reports"
        alpha_root.mkdir(parents=True, exist_ok=True)
        reports_root.mkdir(parents=True, exist_ok=True)

        snapshot_path = Path(snapshot.snapshot_path)
        if not snapshot_path.exists():
            raise RuntimeError("Snapshot path does not exist")

        # Safety contract: alpha code must never mutate original immutable snapshot.
        if workspace.resolve().is_relative_to(snapshot_path.resolve()):
            raise RuntimeError("Invalid workspace location: alpha workspace cannot be nested under snapshot path")

        shutil.copytree(snapshot_path, alpha_root, dirs_exist_ok=True)

        # Structured report files required by product definition.
        variant_data = json.loads(variant.variant_json)
        workflow_reference = _build_workflow_reference(variant_data)
        summary = {
            "run_id": run.id,
            "status": "completed",
            "variant": variant.title,
            "major_changes": variant_data.get("major_changes", []),
            "workflow_reference": workflow_reference,
            "deep_plan_report": deep_plan.markdown_path,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Include deep plan artifacts in the packaged run output.
        deep_plan_md = Path(deep_plan.markdown_path)
        deep_plan_json = Path(deep_plan.json_path)
        if deep_plan_md.exists():
            shutil.copy2(deep_plan_md, reports_root / "deep_plan.md")
        if deep_plan_json.exists():
            shutil.copy2(deep_plan_json, reports_root / "deep_plan.json")

        deep_plan_text = deep_plan_md.read_text(encoding="utf-8") if deep_plan_md.exists() else ""
        AlphaCodegenPipeline = _load_alpha_pipeline_class()
        pipeline_summary = AlphaCodegenPipeline().run(
            alpha_root=alpha_root,
            snapshot_path=snapshot_path,
            variant=variant_data,
            deep_plan_markdown=deep_plan_text,
        )
        (reports_root / "parallel_pipeline_report.json").write_text(
            json.dumps(pipeline_summary, indent=2),
            encoding="utf-8",
        )
        pipeline_md = [
            "# Alpha Parallel Pipeline Report",
            "",
            f"- pipeline: {pipeline_summary.get('pipeline')}",
            f"- generated_at: {pipeline_summary.get('generated_at')}",
            f"- quality_gates: {pipeline_summary.get('quality_gates')}",
            "",
            "## Transformation Steps",
        ]
        for row in pipeline_summary.get("transformation_steps", []):
            pipeline_md.append(f"- [{row.get('step')}] {row.get('name')} ({row.get('type')})")
        (reports_root / "parallel_pipeline_report.md").write_text("\n".join(pipeline_md), encoding="utf-8")

        transform_summary = _apply_variant_transformations(
            alpha_root=alpha_root,
            snapshot_root=snapshot_path,
            reports_root=reports_root,
            variant_data=variant_data,
            deep_plan_text=deep_plan_text,
        )

        repository = db.query(ConnectedRepository).filter(ConnectedRepository.id == run.repository_id).first()
        if not repository:
            raise RuntimeError("Connected repository missing for alpha run")

        context_doc = _write_deep_context_docs(
            reports_root=reports_root,
            run=run,
            repository=repository,
            snapshot=snapshot,
            variant=variant,
            deep_plan=deep_plan,
            alpha_root=alpha_root,
        )

        summary["parallel_pipeline"] = {
            "quality_gates": pipeline_summary.get("quality_gates", {}),
            "transformation_steps": pipeline_summary.get("transformation_steps", []),
        }
        summary["applied_transformations"] = transform_summary
        summary["context_docs"] = context_doc

        (reports_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        test_output = "Test execution skipped: no deterministic framework auto-detected."
        pytest_ini = alpha_root / "pytest.ini"
        requirements = alpha_root / "requirements.txt"
        package_json = alpha_root / "package.json"

        try:
            if pytest_ini.exists() or requirements.exists():
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q"],
                    cwd=str(alpha_root),
                    capture_output=True,
                    text=True,
                    timeout=max(60, settings.ALPHA_CODE_TIMEOUT_MINUTES * 60),
                )
                test_output = (result.stdout or "") + "\n" + (result.stderr or "")
            elif package_json.exists():
                result = subprocess.run(
                    ["npm", "test", "--", "--watch=false"],
                    cwd=str(alpha_root),
                    capture_output=True,
                    text=True,
                    timeout=max(60, settings.ALPHA_CODE_TIMEOUT_MINUTES * 60),
                )
                test_output = (result.stdout or "") + "\n" + (result.stderr or "")
        except Exception as exc:
            test_output = f"Test execution failed: {exc}"

        (reports_root / "test_logs.txt").write_text(test_output, encoding="utf-8")

        zip_path = workspace / "artifacts" / f"alpha_code_{run.id}.zip"
        _zip_directory(workspace, zip_path)

        run.status = "completed"
        run.zip_path = str(zip_path)
        run.summary_json = json.dumps(summary)
        run.completed_at = datetime.utcnow()
        db.commit()

        user = db.query(User).filter(User.tenant_id == run.tenant_id, User.is_active == True).order_by(User.created_at.asc()).first()
        if user and user.email:
            NotificationService.send_alpha_code_status(
                to_email=user.email,
                run_id=run.id,
                status="completed",
                summary="Your alpha code artifact is ready for download in Nexarch.",
            )
    except Exception as exc:
        run = db.query(AlphaCodeRun).filter(AlphaCodeRun.id == run_id).first()
        if run:
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = datetime.utcnow()
            db.commit()

            user = db.query(User).filter(User.tenant_id == run.tenant_id, User.is_active == True).order_by(User.created_at.asc()).first()
            if user and user.email:
                NotificationService.send_alpha_code_status(
                    to_email=user.email,
                    run_id=run.id,
                    status="failed",
                    summary=f"Alpha code generation failed: {run.error_message}",
                )
    finally:
        db.close()


@router.post("/plan-deeply")
def plan_deeply(
    payload: PlanDeeplyRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    variant = (
        db.query(ArchitectureVariant)
        .filter(ArchitectureVariant.id == payload.architecture_variant_id, ArchitectureVariant.tenant_id == tenant_id)
        .first()
    )
    if not variant:
        raise HTTPException(status_code=404, detail="Architecture variant not found")

    doc = db.query(ArchitectureDocument).filter(ArchitectureDocument.id == variant.architecture_document_id).first()
    snapshot = db.query(RepoSnapshot).filter(RepoSnapshot.id == doc.snapshot_id).first() if doc else None
    repository = db.query(ConnectedRepository).filter(ConnectedRepository.id == doc.repository_id).first() if doc else None

    if not doc or not snapshot or not repository:
        raise HTTPException(status_code=400, detail="Variant context is incomplete")

    plan_files = _write_deep_plan(tenant_id, variant, repository, snapshot)

    row = DeepPlanReport(
        id=plan_files["plan_id"],
        tenant_id=tenant_id,
        architecture_variant_id=variant.id,
        markdown_path=plan_files["markdown_path"],
        json_path=plan_files["json_path"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "deep_plan_report_id": row.id,
        "markdown_path": row.markdown_path,
        "json_path": row.json_path,
        "status": "completed",
    }


@router.post("/runs")
def start_alpha_code_run(
    payload: StartAlphaCodeRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    variant = (
        db.query(ArchitectureVariant)
        .filter(ArchitectureVariant.id == payload.architecture_variant_id, ArchitectureVariant.tenant_id == tenant_id)
        .first()
    )
    if not variant:
        raise HTTPException(status_code=404, detail="Architecture variant not found")

    deep_plan = (
        db.query(DeepPlanReport)
        .filter(DeepPlanReport.id == payload.deep_plan_report_id, DeepPlanReport.tenant_id == tenant_id)
        .first()
    )
    if not deep_plan or deep_plan.architecture_variant_id != variant.id:
        raise HTTPException(status_code=400, detail="Valid deep plan report is required before alpha code generation")

    doc = db.query(ArchitectureDocument).filter(ArchitectureDocument.id == variant.architecture_document_id).first()
    if not doc:
        raise HTTPException(status_code=400, detail="Architecture document missing")

    run_id = str(uuid.uuid4())
    workspace = _workspace_root() / tenant_id / doc.repository_id / "alpha_runs" / run_id
    workspace.mkdir(parents=True, exist_ok=True)

    snapshot = db.query(RepoSnapshot).filter(RepoSnapshot.id == doc.snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=400, detail="Snapshot missing")

    variant_data = json.loads(variant.variant_json)
    estimated_seconds = _estimate_alpha_execution_seconds(snapshot, variant_data, deep_plan)
    execution_mode = _resolve_alpha_mode(estimated_seconds)

    run = AlphaCodeRun(
        id=run_id,
        tenant_id=tenant_id,
        repository_id=doc.repository_id,
        snapshot_id=doc.snapshot_id,
        architecture_variant_id=variant.id,
        deep_plan_report_id=deep_plan.id,
        status="pending",
        workspace_path=str(workspace),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    if execution_mode == "sync":
        _execute_alpha_run(SessionLocal, run.id)
        db.refresh(run)
    else:
        background_tasks.add_task(_execute_alpha_run, SessionLocal, run.id)

    return {
        "run_id": run.id,
        "status": run.status,
        "execution_mode": execution_mode,
        "estimated_seconds": estimated_seconds,
        "sync_target_seconds": settings.SYSTEM_ARCH_SYNC_TARGET_SECONDS,
        "selected_architecture_variant_id": variant.id,
    }


@router.get("/runs")
def list_alpha_runs(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    runs = (
        db.query(AlphaCodeRun)
        .filter(AlphaCodeRun.tenant_id == tenant_id)
        .order_by(AlphaCodeRun.created_at.desc())
        .all()
    )
    return [
        {
            "run_id": row.id,
            "status": row.status,
            "repository_id": row.repository_id,
            "snapshot_id": row.snapshot_id,
            "architecture_variant_id": row.architecture_variant_id,
            "zip_path": row.zip_path,
            "error_message": row.error_message,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in runs
    ]


@router.get("/runs/{run_id}")
def get_alpha_run(
    run_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = (
        db.query(AlphaCodeRun)
        .filter(AlphaCodeRun.id == run_id, AlphaCodeRun.tenant_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    summary = json.loads(row.summary_json) if row.summary_json else {}
    return {
        "run_id": row.id,
        "status": row.status,
        "repository_id": row.repository_id,
        "snapshot_id": row.snapshot_id,
        "architecture_variant_id": row.architecture_variant_id,
        "deep_plan_report_id": row.deep_plan_report_id,
        "zip_path": row.zip_path,
        "summary": summary,
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/runs/{run_id}/download")
def download_alpha_zip(
    run_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
):
    row = (
        db.query(AlphaCodeRun)
        .filter(AlphaCodeRun.id == run_id, AlphaCodeRun.tenant_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row.status != "completed" or not row.zip_path:
        raise HTTPException(status_code=400, detail="Zip artifact not ready")

    zip_path = Path(row.zip_path)
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file missing")

    return FileResponse(path=str(zip_path), media_type="application/zip", filename=zip_path.name)


@router.post("/sandbox/sessions")
def create_sandbox_session(
    payload: CreateSandboxSessionRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    run = (
        db.query(AlphaCodeRun)
        .filter(AlphaCodeRun.id == payload.alpha_run_id, AlphaCodeRun.tenant_id == tenant_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Alpha run not found")
    if run.status != "completed":
        raise HTTPException(status_code=400, detail="Sandbox can only be created from a completed alpha run")

    runtime_backend = _sandbox_runtime_backend()
    if runtime_backend == "acr":
        ready = _ensure_acr_runtime_ready(timeout_seconds=180)
        if not ready.get("ok"):
            details = (ready.get("details") or "").strip()
            message = str(ready.get("error") or "ACR sandbox runtime is not ready")
            if details:
                message = f"{message}: {details}"
            raise HTTPException(status_code=503, detail=message)

    active_count = _count_active_sandbox_sessions(db, tenant_id)
    max_active = _sandbox_max_active_sessions()
    if active_count >= max_active:
        raise HTTPException(status_code=429, detail=f"Max concurrent sandboxes reached ({max_active})")

    session_id = str(uuid.uuid4())
    now = datetime.utcnow()
    persistent_root = _sandbox_root(tenant_id, run.repository_id) / session_id
    workspace_path = persistent_root / "workspace"
    uploaded_tests_path = persistent_root / "uploaded_tests"
    uploaded_tests_path.mkdir(parents=True, exist_ok=True)

    _prepare_sandbox_workspace_from_run(run=run, target_workspace=workspace_path)
    stack_type = _detect_stack_type(workspace_path)

    row = AlphaSandboxSession(
        id=session_id,
        tenant_id=tenant_id,
        repository_id=run.repository_id,
        alpha_run_id=run.id,
        workspace_path=str(workspace_path),
        persistent_root=str(persistent_root),
        uploaded_tests_path=str(uploaded_tests_path),
        stack_type=stack_type,
        status="running",
        started_at=now,
        last_activity_at=now,
        expires_at=now + _sandbox_idle_timeout_delta(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "session": _serialize_sandbox_session(row),
        "runtime": _sandbox_runtime_metadata(),
        "limits": {
            "max_concurrent_per_user": max_active,
            "idle_timeout_minutes": int(settings.ALPHA_SANDBOX_IDLE_TIMEOUT_MINUTES),
            "max_upload_files": int(settings.ALPHA_SANDBOX_MAX_UPLOAD_FILES),
            "max_upload_total_mb": int(settings.ALPHA_SANDBOX_MAX_UPLOAD_TOTAL_MB),
            "autofix_max_attempts": int(settings.ALPHA_SANDBOX_AUTOFIX_MAX_ATTEMPTS),
        },
    }


@router.get("/sandbox/sessions")
def list_sandbox_sessions(
    alpha_run_id: Optional[str] = None,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rows = (
        db.query(AlphaSandboxSession)
        .filter(AlphaSandboxSession.tenant_id == tenant_id)
        .order_by(AlphaSandboxSession.created_at.desc())
        .all()
    )

    sessions: List[Dict[str, Any]] = []
    for row in rows:
        _expire_if_idle(db, row)
        if alpha_run_id and row.alpha_run_id != alpha_run_id:
            continue
        sessions.append(_serialize_sandbox_session(row))

    return {
        "sessions": sessions,
        "runtime": _sandbox_runtime_metadata(),
        "active_count": _count_active_sandbox_sessions(db, tenant_id),
        "max_concurrent_per_user": _sandbox_max_active_sessions(),
    }


@router.get("/sandbox/sessions/{session_id}")
def get_sandbox_session(
    session_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = _get_sandbox_session_or_404(db, tenant_id, session_id)
    logs = (
        db.query(AlphaSandboxExecution)
        .filter(AlphaSandboxExecution.tenant_id == tenant_id, AlphaSandboxExecution.session_id == session_id)
        .order_by(AlphaSandboxExecution.created_at.desc())
        .limit(30)
        .all()
    )
    return {
        "session": _serialize_sandbox_session(row),
        "runtime": _sandbox_runtime_metadata(),
        "logs": [_serialize_sandbox_execution(item) for item in logs],
    }


@router.post("/sandbox/sessions/{session_id}/start")
def start_sandbox_session(
    session_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = _get_sandbox_session_or_404(db, tenant_id, session_id)
    if row.status == "running":
        _touch_session(db, row)
        return {"session": _serialize_sandbox_session(row)}

    active_count = _count_active_sandbox_sessions(db, tenant_id)
    max_active = _sandbox_max_active_sessions()
    if active_count >= max_active:
        raise HTTPException(status_code=429, detail=f"Max concurrent sandboxes reached ({max_active})")

    now = datetime.utcnow()
    row.status = "running"
    row.error_message = None
    row.started_at = row.started_at or now
    row.stopped_at = None
    row.last_activity_at = now
    row.expires_at = now + _sandbox_idle_timeout_delta()
    db.commit()
    db.refresh(row)
    return {"session": _serialize_sandbox_session(row)}


@router.post("/sandbox/sessions/{session_id}/stop")
def stop_sandbox_session(
    session_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = _get_sandbox_session_or_404(db, tenant_id, session_id)
    row.status = "stopped"
    row.stopped_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return {"session": _serialize_sandbox_session(row)}


@router.post("/sandbox/sessions/{session_id}/commands")
def run_sandbox_command(
    session_id: str,
    payload: SandboxCommandRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = _get_sandbox_session_or_404(db, tenant_id, session_id)
    _ensure_running_session(db, row)

    workspace = Path(row.workspace_path)
    if not workspace.exists():
        raise HTTPException(status_code=400, detail="Sandbox workspace does not exist")
    if not payload.command or not payload.command.strip():
        raise HTTPException(status_code=400, detail="Command is required")

    timeout_seconds = payload.timeout_seconds or int(settings.ALPHA_SANDBOX_COMMAND_TIMEOUT_SECONDS)
    result = _run_sandbox_runtime_command(
        command=payload.command.strip(),
        cwd=workspace,
        timeout_seconds=timeout_seconds,
        session=row,
    )
    execution = _record_sandbox_execution(
        db=db,
        tenant_id=tenant_id,
        session_id=row.id,
        action_type="command",
        command_text=payload.command.strip(),
        result=result,
        metadata={"timeout_seconds": timeout_seconds},
    )
    _touch_session(db, row)
    return {
        "session": _serialize_sandbox_session(row),
        "runtime": _sandbox_runtime_metadata(),
        "execution": _serialize_sandbox_execution(execution),
    }


@router.post("/sandbox/sessions/{session_id}/tests/upload")
def upload_sandbox_tests(
    session_id: str,
    files: List[UploadFile] = File(...),
    target_subdir: str = Form("uploaded_tests"),
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = _get_sandbox_session_or_404(db, tenant_id, session_id)
    _ensure_running_session(db, row)
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    base_uploaded_path = Path(row.uploaded_tests_path)
    base_uploaded_path.mkdir(parents=True, exist_ok=True)
    subdir = _validate_safe_relative_upload_path(target_subdir)

    pending_writes: List[Dict[str, Any]] = []
    total_bytes = 0
    for upload in files:
        safe_name = _validate_safe_relative_upload_path(upload.filename or f"upload_{uuid.uuid4().hex}.txt")
        relative_path = subdir / safe_name
        body = upload.file.read()
        body_size = len(body)
        total_bytes += body_size
        pending_writes.append({
            "relative_path": relative_path,
            "bytes": body,
            "size": body_size,
        })
        upload.file.close()

    _enforce_upload_limits(file_count=len(pending_writes), total_bytes=total_bytes)

    uploaded_files: List[str] = []
    resolved_base = base_uploaded_path.resolve()
    for item in pending_writes:
        destination = (base_uploaded_path / item["relative_path"]).resolve()
        if not destination.is_relative_to(resolved_base):
            raise HTTPException(status_code=400, detail="Invalid upload destination")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(item["bytes"])
        uploaded_files.append(str(destination.relative_to(base_uploaded_path)))

    _touch_session(db, row)
    return {
        "session": _serialize_sandbox_session(row),
        "uploaded_count": len(uploaded_files),
        "uploaded_total_bytes": total_bytes,
        "files": uploaded_files,
    }


@router.post("/sandbox/sessions/{session_id}/tests/run")
def run_sandbox_tests(
    session_id: str,
    payload: SandboxTestRunRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = _get_sandbox_session_or_404(db, tenant_id, session_id)
    _ensure_running_session(db, row)

    workspace = Path(row.workspace_path)
    uploaded_tests_path = Path(row.uploaded_tests_path)
    if not workspace.exists():
        raise HTTPException(status_code=400, detail="Sandbox workspace does not exist")

    timeout_seconds = payload.timeout_seconds or int(settings.ALPHA_SANDBOX_COMMAND_TIMEOUT_SECONDS)
    runtime_backend = _sandbox_runtime_backend()
    commands = _build_test_command_set(
        workspace=workspace,
        uploaded_tests_path=uploaded_tests_path,
        mode=payload.mode,
        custom_command=payload.custom_command,
        runtime_backend=runtime_backend,
    )
    if not commands:
        raise HTTPException(status_code=400, detail="No tests discovered. Upload tests or provide a custom command")

    test_result = _run_test_suite(
        workspace=workspace,
        commands=commands,
        timeout_seconds=timeout_seconds,
        session=row,
    )
    execution = _record_sandbox_execution(
        db=db,
        tenant_id=tenant_id,
        session_id=row.id,
        action_type="tests",
        command_text=" && ".join(commands),
        result={
            "exit_code": test_result.get("exit_code", 1),
            "stdout": test_result.get("stdout", ""),
            "stderr": test_result.get("stderr", ""),
        },
        metadata={
            "mode": payload.mode,
            "commands": commands,
            "command_results": test_result.get("command_results", []),
        },
    )

    _touch_session(db, row)
    return {
        "session": _serialize_sandbox_session(row),
        "runtime": _sandbox_runtime_metadata(),
        "tests": test_result,
        "execution": _serialize_sandbox_execution(execution),
    }


@router.post("/sandbox/sessions/{session_id}/autofix")
def run_sandbox_autofix(
    session_id: str,
    payload: SandboxAutofixRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = _get_sandbox_session_or_404(db, tenant_id, session_id)
    _ensure_running_session(db, row)

    workspace = Path(row.workspace_path)
    uploaded_tests_path = Path(row.uploaded_tests_path)
    if not workspace.exists():
        raise HTTPException(status_code=400, detail="Sandbox workspace does not exist")

    configured_max = max(1, int(settings.ALPHA_SANDBOX_AUTOFIX_MAX_ATTEMPTS))
    max_attempts = configured_max
    if payload.max_attempts is not None:
        max_attempts = max(1, min(configured_max, int(payload.max_attempts)))

    timeout_seconds = int(settings.ALPHA_SANDBOX_COMMAND_TIMEOUT_SECONDS)
    runtime_backend = _sandbox_runtime_backend()
    commands = _build_test_command_set(
        workspace=workspace,
        uploaded_tests_path=uploaded_tests_path,
        mode=payload.mode,
        custom_command=None,
        runtime_backend=runtime_backend,
    )
    if not commands:
        raise HTTPException(status_code=400, detail="No tests discovered for autofix")

    attempts: List[Dict[str, Any]] = []
    fixed = False
    last_test_result: Dict[str, Any] = {}

    for attempt_index in range(1, max_attempts + 1):
        test_result = _run_test_suite(
            workspace=workspace,
            commands=commands,
            timeout_seconds=timeout_seconds,
            session=row,
        )
        last_test_result = test_result
        attempt_row: Dict[str, Any] = {
            "attempt": attempt_index,
            "tests": {
                "success": bool(test_result.get("success")),
                "exit_code": test_result.get("exit_code"),
                "commands": test_result.get("commands_executed", []),
                "command_results": test_result.get("command_results", []),
            },
        }

        if test_result.get("success"):
            fixed = True
            attempts.append(attempt_row)
            break

        combined_output = (test_result.get("stdout") or "") + "\n" + (test_result.get("stderr") or "")
        fix_result = _attempt_dependency_fix(
            workspace=workspace,
            combined_output=combined_output,
            timeout_seconds=timeout_seconds,
            session=row,
        )
        attempt_row["fix"] = {
            "applied": bool(fix_result.get("applied")),
            "all_success": bool(fix_result.get("all_success")),
            "actions": fix_result.get("actions", []),
        }
        attempts.append(attempt_row)

        if not fix_result.get("applied"):
            break

    summary = {
        "fixed": fixed,
        "attempts": attempts,
        "max_attempts": max_attempts,
        "final_test_success": bool(last_test_result.get("success")),
        "commands": commands,
    }
    execution = _record_sandbox_execution(
        db=db,
        tenant_id=tenant_id,
        session_id=row.id,
        action_type="autofix",
        command_text="autofix",
        result={
            "exit_code": 0 if fixed else 1,
            "stdout": json.dumps(summary, indent=2),
            "stderr": "" if fixed else "Autofix reached limit without passing tests",
        },
        metadata=summary,
    )

    _touch_session(db, row)
    return {
        "session": _serialize_sandbox_session(row),
        "runtime": _sandbox_runtime_metadata(),
        "autofix": summary,
        "execution": _serialize_sandbox_execution(execution),
    }


@router.post("/sandbox/sessions/{session_id}/validate-auto")
def run_sandbox_auto_validation(
    session_id: str,
    payload: Optional[SandboxAutoValidationRequest] = None,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = _get_sandbox_session_or_404(db, tenant_id, session_id)
    _ensure_running_session(db, row)

    summary = _run_langgraph_auto_validation(
        db=db,
        row=row,
        max_attempts=(payload.max_attempts if payload else None),
    )

    execution = _record_sandbox_execution(
        db=db,
        tenant_id=tenant_id,
        session_id=row.id,
        action_type="auto_validation",
        command_text="langgraph_auto_validation",
        result={
            "exit_code": 0 if summary.get("passed") else 1,
            "stdout": json.dumps(summary, indent=2),
            "stderr": "" if summary.get("passed") else "Auto validation finished without full pass",
        },
        metadata=summary,
    )

    _touch_session(db, row)
    email_notification = _notify_sandbox_validation_status(
        db=db,
        row=row,
        passed=bool(summary.get("passed")),
        attempts_count=len(summary.get("attempts") or []),
    )
    return {
        "session": _serialize_sandbox_session(row),
        "runtime": _sandbox_runtime_metadata(),
        "automation": summary,
        "execution": _serialize_sandbox_execution(execution),
        "email_notification": email_notification,
    }


@router.get("/sandbox/sessions/{session_id}/logs")
def list_sandbox_logs(
    session_id: str,
    limit: int = 50,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = _get_sandbox_session_or_404(db, tenant_id, session_id)
    bounded_limit = max(1, min(200, int(limit)))
    executions = (
        db.query(AlphaSandboxExecution)
        .filter(AlphaSandboxExecution.tenant_id == tenant_id, AlphaSandboxExecution.session_id == session_id)
        .order_by(AlphaSandboxExecution.created_at.desc())
        .limit(bounded_limit)
        .all()
    )
    return {
        "session": _serialize_sandbox_session(row),
        "runtime": _sandbox_runtime_metadata(),
        "logs": [_serialize_sandbox_execution(item) for item in executions],
    }
