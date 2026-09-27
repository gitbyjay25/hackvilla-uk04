from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import traceback
import zipfile
import uuid
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.config import get_settings
from db.base import SessionLocal, get_db
from db.models import (
    ArchitectureDocument,
    ArchitectureVariantReport,
    ArchitectureVariant,
    ConnectedRepository,
    GitHubInstallation,
    Project,
    RepoSnapshot,
    Span,
    User,
)
from dependencies.auth import get_tenant_id_from_jwt
from services.architecture_report_service import generate_variant_report_artifacts
from services.github_app_service import GitHubAppService
from services.notification_service import NotificationService


router = APIRouter(prefix="/api/v1/system-architecture", tags=["system-architecture"])
settings = get_settings()


_VARIANT_JOBS: Dict[str, Dict[str, Any]] = {}

_DEPENDENCY_HINT_STOPWORDS = {
    "a", "an", "and", "api", "app", "application", "apps", "arch", "architecture",
    "aside", "async", "auth", "blog", "build", "cache", "caching", "client", "code",
    "component", "components", "concurrent", "config", "connection", "core", "current",
    "data", "demo", "dependency", "dependencies", "design", "diagram", "edge", "fast",
    "flow", "generated", "generator", "http", "info", "layer", "layout", "module",
    "node", "nodes", "page", "path", "pipeline", "plan", "project", "report", "runtime",
    "service", "services", "source", "stack", "system", "test", "tests", "tool", "unknown",
    "server", "backend", "frontend", "main", "index", "helper", "helpers", "internal",
    "use", "version", "versions", "workflow", "with",
}

_DEPENDENCY_REGISTRY_CACHE: Dict[str, Dict[str, Any]] = {}
_PYTHON_IMPORT_SKIP = {
    "os", "sys", "re", "json", "time", "math", "typing", "pathlib", "collections", "datetime",
    "itertools", "functools", "asyncio", "subprocess", "logging", "traceback", "unittest",
    "pytest", "setuptools", "pip", "wheel",
}
_NPM_PREFERRED_HINTS = {
    "react", "next", "vue", "svelte", "angular", "axios", "vite", "webpack", "express",
    "nestjs", "koa", "typeorm", "prisma", "mongoose", "socket.io",
}
_DEPENDENCY_REASONING_MAP: Dict[str, List[str]] = {
    "cache": ["redis", "orjson"],
    "latency": ["redis", "uvloop"],
    "queue": ["celery", "redis"],
    "async": ["httpx", "celery"],
    "database": ["sqlalchemy", "alembic"],
    "postgres": ["sqlalchemy", "psycopg2-binary"],
    "mysql": ["sqlalchemy", "pymysql"],
    "mongo": ["pymongo"],
    "auth": ["pyjwt", "passlib"],
    "api": ["fastapi", "pydantic"],
    "frontend": ["react", "next"],
    "observability": ["opentelemetry-api", "opentelemetry-sdk"],
    "metrics": ["prometheus-client"],
}


def _is_plausible_dependency_name(name: str) -> bool:
    candidate = str(name or "").strip().lower()
    if not candidate:
        return False
    if len(candidate) < 2 or len(candidate) > 100:
        return False
    if candidate in _DEPENDENCY_HINT_STOPWORDS:
        return False
    if candidate.endswith("-demo") or candidate.endswith("_demo"):
        return False
    if candidate.startswith("blog-") and "generator" in candidate:
        return False
    if not re.fullmatch(r"[@a-z0-9][@a-z0-9._/\-]*", candidate):
        return False
    if not any(ch.isalpha() for ch in candidate):
        return False
    return True


def _sanitize_dependency_hints(values: List[str]) -> List[str]:
    cleaned = {str(item).strip().lower() for item in (values or []) if _is_plausible_dependency_name(str(item))}
    return sorted(cleaned)


def _version_sort_key(version: str) -> tuple:
    numeric = [int(part) for part in re.findall(r"\d+", str(version or ""))]
    return tuple(numeric) if numeric else (0,)


def _is_prerelease(version: str) -> bool:
    return bool(re.search(r"(?:a|b|rc|alpha|beta|pre|dev)", str(version or "").lower()))


def _normalize_dependency_version(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "unspecified"

    token = text.split(";", 1)[0].strip()
    token = token.split(",", 1)[0].strip()
    token = token.replace("^", "").replace("~", "")
    match = re.search(r"\d+(?:\.\d+){0,3}(?:[-+][a-z0-9\.]+)?", token, flags=re.IGNORECASE)
    return match.group(0) if match else (token or "unspecified")


def _detect_dependency_ecosystem(name: str, source: str = "") -> str:
    dep_name = str(name or "").strip().lower()
    dep_source = str(source or "").strip().lower()
    if dep_source.endswith("package.json") or dep_name.startswith("@") or dep_name in _NPM_PREFERRED_HINTS:
        return "npm"
    return "pypi"


def _fetch_latest_pypi(name: str) -> Dict[str, Any]:
    cache_key = f"pypi:{name.lower()}"
    if cache_key in _DEPENDENCY_REGISTRY_CACHE:
        return _DEPENDENCY_REGISTRY_CACHE[cache_key]

    url = f"https://pypi.org/pypi/{name}/json"
    result: Dict[str, Any] = {
        "latest_version": None,
        "registry_url": url,
        "validation_source": "pypi",
    }
    try:
        response = requests.get(url, timeout=8)
        if response.ok:
            payload = response.json()
            info = payload.get("info") or {}
            releases = payload.get("releases") or {}
            latest = str(info.get("version") or "").strip() or None
            if latest and _is_prerelease(latest):
                stable_versions = [v for v in releases.keys() if not _is_prerelease(v)]
                if stable_versions:
                    latest = sorted(stable_versions, key=_version_sort_key)[-1]
            result["latest_version"] = latest
    except Exception:
        pass

    _DEPENDENCY_REGISTRY_CACHE[cache_key] = result
    return result


def _fetch_latest_npm(name: str) -> Dict[str, Any]:
    cache_key = f"npm:{name.lower()}"
    if cache_key in _DEPENDENCY_REGISTRY_CACHE:
        return _DEPENDENCY_REGISTRY_CACHE[cache_key]

    encoded_name = name.replace("/", "%2F")
    url = f"https://registry.npmjs.org/{encoded_name}"
    result: Dict[str, Any] = {
        "latest_version": None,
        "registry_url": f"https://www.npmjs.com/package/{name}",
        "validation_source": "npm",
    }
    try:
        response = requests.get(url, timeout=8)
        if response.ok:
            payload = response.json()
            latest = str(((payload.get("dist-tags") or {}).get("latest") or "")).strip() or None
            result["latest_version"] = latest
    except Exception:
        pass

    _DEPENDENCY_REGISTRY_CACHE[cache_key] = result
    return result


def _validate_dependency_version(name: str, version: str, source: str = "") -> Dict[str, Any]:
    ecosystem = _detect_dependency_ecosystem(name, source)
    registry_meta = _fetch_latest_npm(name) if ecosystem == "npm" else _fetch_latest_pypi(name)

    current = _normalize_dependency_version(version)
    latest = _normalize_dependency_version(str(registry_meta.get("latest_version") or ""))
    latest = latest if latest != "unspecified" else None

    resolved_version = current
    status = "declared_unverified"
    if current == "unspecified" and latest:
        resolved_version = latest
        status = "resolved_from_registry"
    elif current != "unspecified" and latest and current == latest:
        status = "validated_up_to_date"
    elif current != "unspecified" and latest and current != latest:
        status = "validated_update_available"
    elif current == "unspecified" and not latest:
        status = "registry_not_found"

    return {
        "ecosystem": ecosystem,
        "resolved_version": resolved_version,
        "latest_version": latest,
        "validation_status": status,
        "validation_source": registry_meta.get("validation_source"),
        "registry_url": registry_meta.get("registry_url"),
    }


def _extract_doc_dependency_hints(content: str) -> List[str]:
    text = str(content or "")
    hints: List[str] = []
    for pattern in [
        r"pip\s+install\s+([@A-Za-z0-9_./\-]+)",
        r"npm\s+install\s+([@A-Za-z0-9_./\-]+)",
        r"pnpm\s+add\s+([@A-Za-z0-9_./\-]+)",
        r"yarn\s+add\s+([@A-Za-z0-9_./\-]+)",
    ]:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            token = str(match).strip().lower()
            if _is_plausible_dependency_name(token):
                hints.append(token)
    return hints


def _extract_python_import_hints(content: str) -> List[str]:
    hints: List[str] = []
    text = str(content or "")
    for match in re.findall(r"^\s*import\s+([a-zA-Z0-9_\.]+)", text, flags=re.MULTILINE):
        token = match.split(".", 1)[0].strip().lower()
        if token and token not in _PYTHON_IMPORT_SKIP and _is_plausible_dependency_name(token):
            hints.append(token)
    for match in re.findall(r"^\s*from\s+([a-zA-Z0-9_\.]+)\s+import\s+", text, flags=re.MULTILINE):
        token = match.split(".", 1)[0].strip().lower()
        if token and token not in _PYTHON_IMPORT_SKIP and _is_plausible_dependency_name(token):
            hints.append(token)
    return hints


def _extract_js_import_hints(content: str) -> List[str]:
    hints: List[str] = []
    text = str(content or "")
    for pattern in [
        r"from\s+['\"]([@A-Za-z0-9_./\-]+)['\"]",
        r"require\(\s*['\"]([@A-Za-z0-9_./\-]+)['\"]\s*\)",
    ]:
        for match in re.findall(pattern, text):
            token = str(match).strip().lower()
            if token.startswith("."):
                continue
            if _is_plausible_dependency_name(token):
                hints.append(token)
    return hints


def _build_contextual_dependency_recommendations(
    profile: str,
    major_changes: List[str],
    static_summary: Dict[str, Any],
    runtime_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    scored: Dict[str, Dict[str, Any]] = {}

    def add(name: str, score: int, source: str, rationale: str) -> None:
        dep_name = str(name or "").strip().lower()
        if not _is_plausible_dependency_name(dep_name):
            return
        row = scored.get(dep_name)
        if not row:
            scored[dep_name] = {
                "name": dep_name,
                "score": score,
                "source": source,
                "rationale": rationale,
            }
            return
        row["score"] += score
        if len(str(rationale)) > len(str(row.get("rationale") or "")):
            row["rationale"] = rationale

    for dep in (static_summary.get("dependency_inventory") or [])[:300]:
        add(dep.get("name"), 8, str(dep.get("source") or "static_inventory"), "Detected directly from dependency manifests.")

    for hint in (static_summary.get("dependency_hints") or [])[:300]:
        add(hint, 5, "static_hints", "Found in static dependency scan.")

    for hint in (static_summary.get("contextual_dependency_hints") or [])[:400]:
        add(hint, 6, "docs_and_code_context", "Found in repository docs or import statements.")

    combined_changes = " ".join(major_changes).lower()
    for token, mapped in _DEPENDENCY_REASONING_MAP.items():
        if token in combined_changes:
            for dep_name in mapped:
                add(dep_name, 7, "langgraph_dependency_reasoning", f"Recommended because architecture changes mention '{token}'.")

    service_text = " ".join([str(s).lower() for s in (runtime_summary.get("services") or [])])
    for token, mapped in _DEPENDENCY_REASONING_MAP.items():
        if token in service_text:
            for dep_name in mapped:
                add(dep_name, 4, "runtime_signals", f"Observed runtime services suggest '{token}' capability.")

    profile_defaults = {
        "cost": ["requests", "httpx", "sqlalchemy", "redis"],
        "scalability": ["fastapi", "redis", "celery", "sqlalchemy"],
        "performance": ["fastapi", "uvloop", "orjson", "redis"],
    }
    for dep_name in profile_defaults.get(profile, ["fastapi", "sqlalchemy", "redis"]):
        add(dep_name, 3, "profile_defaults", f"Baseline dependency for {profile} profile.")

    ranked = sorted(scored.values(), key=lambda row: (-int(row.get("score") or 0), str(row.get("name") or "")))
    return ranked[:14]


class GitHubInstallationUpsert(BaseModel):
    github_installation_id: str
    account_login: str
    account_type: Optional[str] = None


class ConnectRepositoryRequest(BaseModel):
    installation_id: Optional[str] = None
    owner: str
    repo_name: str
    default_branch: str = "main"
    is_private: bool = True
    is_monorepo: bool = True
    remote_url: Optional[str] = None
    local_repo_path: Optional[str] = None


class SnapshotRequest(BaseModel):
    branch: Optional[str] = None
    use_default_branch: bool = True


class AnalyzeRequest(BaseModel):
    snapshot_id: str
    mode: Optional[str] = Field(default=None, pattern="^(async|sync|auto)$")
    telemetry_project_id: Optional[str] = None
    telemetry_service_name: Optional[str] = None
    cost_weight: float = 30.0
    scalability_weight: float = 35.0
    performance_weight: float = 35.0


class GenerateVariantsRequest(BaseModel):
    architecture_document_id: str
    mode: Optional[str] = Field(default=None, pattern="^(async|sync|auto)$")
    cost_weight: float = 30.0
    scalability_weight: float = 35.0
    performance_weight: float = 35.0


class PlanDeeplyRequest(BaseModel):
    architecture_variant_id: str


class GenerateVariantReportRequest(BaseModel):
    include_official_references: bool = True


def _workspace_root() -> Path:
    root = Path(settings.REPO_WORKSPACE_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _repo_size_bytes(path: Path) -> int:
    total = 0
    for current, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".next", "dist", "build", "__pycache__"}]
        for name in files:
            file_path = Path(current) / name
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def _normalize_weights(cost: float, scalability: float, performance: float) -> Dict[str, float]:
    raw = {
        "cost": max(0.0, cost),
        "scalability": max(0.0, scalability),
        "performance": max(0.0, performance),
    }
    if sum(raw.values()) == 0:
        raw = {
            "cost": settings.SYSTEM_ARCH_DEFAULT_COST_WEIGHT,
            "scalability": settings.SYSTEM_ARCH_DEFAULT_SCALABILITY_WEIGHT,
            "performance": settings.SYSTEM_ARCH_DEFAULT_PERFORMANCE_WEIGHT,
        }
    total = sum(raw.values())
    return {
        "raw": raw,
        "normalized": {
            "cost": raw["cost"] / total,
            "scalability": raw["scalability"] / total,
            "performance": raw["performance"] / total,
        },
    }


def _count_runtime_signals(
    db: Session,
    tenant_id: str,
    project_id: Optional[str] = None,
    service_name: Optional[str] = None,
) -> Dict[str, Any]:
    query = db.query(Span).filter(Span.tenant_id == tenant_id)
    if project_id:
        query = query.filter(Span.project_id == project_id)
    if service_name:
        query = query.filter(Span.service_name == service_name)

    spans = query.all()
    services = sorted({s.service_name for s in spans})
    operations = Counter((s.operation or "unknown") for s in spans if (s.operation or "").strip())
    avg_latency = round(
        (sum(float(s.latency_ms or 0.0) for s in spans) / max(1, len(spans))),
        2,
    )
    error_count = sum(1 for s in spans if s.error or ((s.status_code or 0) >= 500))
    project_names = sorted(
        {
            p.name
            for p in db.query(Project).filter(Project.tenant_id == tenant_id).all()
            if p and p.name
        }
    )

    return {
        "total_spans": len(spans),
        "services": services,
        "top_operations": [
            {"operation": name, "count": count}
            for name, count in operations.most_common(12)
        ],
        "avg_latency_ms": avg_latency,
        "error_count": error_count,
        "error_rate": round(error_count / max(1, len(spans)), 4),
        "project_filter": project_id,
        "service_filter": service_name,
        "known_projects": project_names[:200],
    }


def _list_sdk_telemetry_apps(db: Session, tenant_id: str) -> List[Dict[str, Any]]:
    projects = (
        db.query(Project)
        .filter(Project.tenant_id == tenant_id)
        .order_by(Project.created_at.desc())
        .all()
    )
    rows: List[Dict[str, Any]] = []
    seen_ids = set()

    for project in projects:
        span_count = (
            db.query(Span)
            .filter(Span.tenant_id == tenant_id, Span.project_id == project.id)
            .count()
        )
        last_span = (
            db.query(Span)
            .filter(Span.tenant_id == tenant_id, Span.project_id == project.id)
            .order_by(Span.start_time.desc())
            .first()
        )

        rows.append(
            {
                "selector_value": f"project:{project.id}",
                "project_id": project.id,
                "telemetry_project_id": project.id,
                "telemetry_service_name": project.sdk_service_name,
                "app_name": project.name,
                "sdk_service_name": project.sdk_service_name,
                "span_count": span_count,
                "last_seen": last_span.start_time.isoformat() if last_span and last_span.start_time else None,
                "source": "project_table",
            }
        )
        seen_ids.add(project.id)

    # Backward compatibility: surface historical spans that predate project mapping.
    orphan_service_rows = (
        db.query(Span.service_name)
        .filter(Span.tenant_id == tenant_id, Span.project_id.is_(None))
        .distinct()
        .all()
    )
    for service_row in orphan_service_rows:
        service_name = str(service_row[0] or "").strip()
        if not service_name:
            continue
        synthetic_id = f"legacy:{service_name}"
        if synthetic_id in seen_ids:
            continue

        span_count = (
            db.query(Span)
            .filter(Span.tenant_id == tenant_id, Span.project_id.is_(None), Span.service_name == service_name)
            .count()
        )
        last_span = (
            db.query(Span)
            .filter(Span.tenant_id == tenant_id, Span.project_id.is_(None), Span.service_name == service_name)
            .order_by(Span.start_time.desc())
            .first()
        )
        rows.append(
            {
                "selector_value": f"legacy:{service_name}",
                "project_id": None,
                "telemetry_project_id": None,
                "telemetry_service_name": service_name,
                "legacy_service_name": service_name,
                "app_name": service_name,
                "sdk_service_name": service_name,
                "span_count": span_count,
                "last_seen": last_span.start_time.isoformat() if last_span and last_span.start_time else None,
                "source": "legacy_span_service",
            }
        )
        seen_ids.add(synthetic_id)

    rows.sort(key=lambda item: item.get("last_seen") or "", reverse=True)
    return rows


def _estimate_variant_generation_seconds(static_summary: Dict[str, Any], runtime_summary: Dict[str, Any]) -> float:
    """Estimate generation time from analysis complexity, not repository size alone."""
    file_count = float(static_summary.get("file_count", 0) or 0)
    dependency_count = float(len(static_summary.get("dependency_files", []) or []))
    db_signal_count = float(len(static_summary.get("database_signals", []) or []))
    runtime_spans = float(runtime_summary.get("total_spans", 0) or 0)
    service_count = float(len(runtime_summary.get("services", []) or []))

    # Heuristic budget: base prompt prep + structure complexity + telemetry complexity.
    estimate = 2.0 + (file_count / 300.0) + (dependency_count / 10.0) + (db_signal_count / 20.0) + (runtime_spans / 5000.0) + (service_count / 5.0)
    return max(1.0, round(estimate, 2))


def _resolve_generation_mode(requested_mode: Optional[str], estimated_seconds: float) -> str:
    """Use sync for quick tasks and async for heavier work based on estimated runtime."""
    target = max(1, int(settings.SYSTEM_ARCH_SYNC_TARGET_SECONDS))
    mode = (requested_mode or settings.SYSTEM_ARCH_AI_MODE or "auto").lower()

    if mode == "async":
        return "async"
    if mode == "sync":
        return "sync" if estimated_seconds <= target else "async"
    return "sync" if estimated_seconds <= target else "async"


def _extract_static_summary(snapshot_path: Path) -> Dict[str, Any]:
    languages: Dict[str, int] = {}
    dependency_files: List[str] = []
    dependency_hints: List[str] = []
    contextual_dependency_hints: List[str] = []
    dependency_inventory: List[Dict[str, Any]] = []
    db_signals: List[str] = []
    parsed_context_files = 0

    def add_dependency(name: str, version: str, source: str, scope: str = "runtime") -> None:
        clean_name = str(name or "").strip().lower()
        if not _is_plausible_dependency_name(clean_name):
            return
        clean_version = str(version or "").strip() or "unspecified"
        dependency_inventory.append(
            {
                "name": clean_name,
                "version": clean_version,
                "source": source,
                "scope": scope,
            }
        )

    for current, dirs, files in os.walk(snapshot_path):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".next", "dist", "build", "__pycache__"}]
        for name in files:
            file_path = Path(current) / name
            ext = file_path.suffix.lower() or "<no_ext>"
            lower_name = name.lower()
            languages[ext] = languages.get(ext, 0) + 1

            if name in {"requirements.txt", "pyproject.toml", "package.json", "pom.xml", "build.gradle"}:
                rel_path = str(file_path.relative_to(snapshot_path))
                dependency_files.append(rel_path)
                try:
                    if name == "requirements.txt":
                        for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if line.startswith(("-e", "git+", "http://", "https://", "-r ")):
                                continue
                            match = re.match(r"([A-Za-z0-9_.\-]+)\s*([<>=!~]{1,2}\s*[^;,\s]+)?", line)
                            if match:
                                add_dependency(
                                    name=match.group(1),
                                    version=(match.group(2) or "unspecified"),
                                    source=rel_path,
                                    scope="runtime",
                                )
                            pkg = re.split(r"[<>=~!\[]", line, maxsplit=1)[0].strip().lower()
                            if _is_plausible_dependency_name(pkg):
                                dependency_hints.append(pkg)
                    elif name == "package.json":
                        package_payload = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
                        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                            for dep_name, dep_version in (package_payload.get(section) or {}).items():
                                dep_name_clean = str(dep_name).strip().lower()
                                if _is_plausible_dependency_name(dep_name_clean):
                                    dependency_hints.append(dep_name_clean)
                                add_dependency(
                                    name=str(dep_name),
                                    version=str(dep_version),
                                    source=rel_path,
                                    scope="runtime" if section == "dependencies" else "build",
                                )
                    elif name == "pyproject.toml":
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        # Parse common pyproject dependency patterns without requiring tomllib.
                        for line in content.splitlines():
                            raw = line.strip()
                            if not raw or raw.startswith("#"):
                                continue

                            quoted_matches = re.findall(r"['\"]([A-Za-z0-9_.\-]+(?:[<>=!~].*?)?)['\"]", raw)
                            for token in quoted_matches:
                                dep_name = re.split(r"[<>=~!\[]", token, maxsplit=1)[0].strip().lower()
                                dep_version = token.replace(dep_name, "", 1).strip() or "unspecified"
                                if _is_plausible_dependency_name(dep_name) and dep_name not in {"python"}:
                                    dependency_hints.append(dep_name)
                                    add_dependency(dep_name, dep_version, rel_path, "runtime")

                            inline_match = re.match(r"([A-Za-z0-9_.\-]+)\s*=\s*['\"]([^'\"]+)['\"]", raw)
                            if inline_match:
                                dep_name = inline_match.group(1).strip().lower()
                                dep_version = inline_match.group(2).strip() or "unspecified"
                                if _is_plausible_dependency_name(dep_name) and dep_name not in {"python", "name", "version", "description"}:
                                    dependency_hints.append(dep_name)
                                    add_dependency(dep_name, dep_version, rel_path, "runtime")
                    else:
                        content = file_path.read_text(encoding="utf-8", errors="ignore").lower()
                        for marker in [
                            "kafka",
                            "rabbitmq",
                            "sqs",
                            "celery",
                            "redis",
                            "memcache",
                            "postgres",
                            "mysql",
                            "mongodb",
                            "dynamodb",
                            "stripe",
                            "twilio",
                            "sendgrid",
                            "grpc",
                        ]:
                            if marker in content:
                                dependency_hints.append(marker)
                except Exception:
                    # Keep extraction resilient even if one manifest is malformed.
                    pass

            if parsed_context_files < 220 and ext in {".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".rst", ".txt"}:
                try:
                    if file_path.stat().st_size <= 250000:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        parsed_context_files += 1

                        extracted: List[str] = []
                        if ext == ".py":
                            extracted = _extract_python_import_hints(content)
                        elif ext in {".js", ".jsx", ".ts", ".tsx"}:
                            extracted = _extract_js_import_hints(content)
                        elif lower_name.startswith("readme") or "guide" in lower_name or "doc" in lower_name or ext in {".md", ".rst", ".txt"}:
                            extracted = _extract_doc_dependency_hints(content)

                        if extracted:
                            dependency_hints.extend(extracted)
                            contextual_dependency_hints.extend(extracted)
                except Exception:
                    pass

            if "migration" in lower_name or "schema" in lower_name or lower_name.endswith(".sql"):
                db_signals.append(str(file_path.relative_to(snapshot_path)))

    top_languages = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10]
    seen = set()
    unique_inventory: List[Dict[str, Any]] = []
    for dep in dependency_inventory:
        key = (dep["name"], dep["version"], dep["source"], dep["scope"])
        if key in seen:
            continue
        seen.add(key)
        unique_inventory.append(dep)

    return {
        "top_file_types": top_languages,
        "dependency_files": dependency_files[:50],
        "dependency_hints": _sanitize_dependency_hints(dependency_hints)[:300],
        "contextual_dependency_hints": _sanitize_dependency_hints(contextual_dependency_hints)[:500],
        "dependency_inventory": unique_inventory[:400],
        "database_signals": db_signals[:100],
        "file_count": sum(languages.values()),
    }


def _slugify_component(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return slug or "component"


def _humanize_component(value: str) -> str:
    text = re.sub(r"[_\-]+", " ", (value or "").strip())
    text = re.sub(r"\s+", " ", text).strip()
    return text.title() if text else "Component"


def _derive_static_service_candidates(snapshot_path: Path, limit: int = 12) -> List[Dict[str, Any]]:
    if not snapshot_path.exists() or not snapshot_path.is_dir():
        return []

    code_extensions = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".cs", ".php", ".rb", ".kt"
    }
    ignored_dirs = {".git", "node_modules", ".next", "dist", "build", "__pycache__", "coverage", ".venv", "venv"}
    generic_parts = {
        "src", "app", "server", "backend", "frontend", "core", "lib", "common", "shared", "utils", "module", "modules", "pkg", "packages", "internal"
    }

    scores: Counter = Counter()
    samples: Dict[str, str] = {}

    for current, dirs, files in os.walk(snapshot_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        current_path = Path(current)

        for name in files:
            file_path = current_path / name
            if file_path.suffix.lower() not in code_extensions:
                continue

            rel = file_path.relative_to(snapshot_path)
            parts = [p for p in rel.parts if p and not p.startswith(".")]
            if not parts:
                continue

            candidate = ""
            if len(parts) >= 2 and parts[0].lower() in {"src", "app", "server", "backend", "frontend", "services", "service", "modules", "packages", "apps"}:
                candidate = parts[1]
            elif len(parts) >= 3 and parts[1].lower() in {"controllers", "controller", "handlers", "routes", "routers", "api", "services", "service"}:
                candidate = parts[0]
            else:
                candidate = parts[0]

            key = _slugify_component(candidate)
            if key in generic_parts or key in {"tests", "test", "scripts", "docs"}:
                continue

            scores[key] += 1
            samples.setdefault(key, str(rel).replace("\\", "/"))

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "id": key,
            "label": _humanize_component(key),
            "score": score,
            "sample_path": samples.get(key, ""),
        }
        for key, score in ordered[:limit]
    ]


def _derive_data_store_candidates(snapshot_path: Path, dependency_text: str, db_signals: List[str], limit: int = 4) -> List[Dict[str, str]]:
    hints = f"{dependency_text} {' '.join(db_signals).lower()}"
    ordered_markers = [
        ("postgres", "PostgreSQL"),
        ("mysql", "MySQL"),
        ("mariadb", "MariaDB"),
        ("mongodb", "MongoDB"),
        ("dynamodb", "DynamoDB"),
        ("cassandra", "Cassandra"),
        ("sqlite", "SQLite"),
        ("redis", "Redis"),
        ("elasticsearch", "Elasticsearch"),
    ]

    found: List[Dict[str, str]] = []
    seen = set()
    for marker, label in ordered_markers:
        if marker in hints and marker not in seen:
            found.append({"id": _slugify_component(marker), "label": label})
            seen.add(marker)
        if len(found) >= limit:
            break

    if found:
        return found

    if db_signals:
        return [{"id": "primary_data_store", "label": "Primary Data Store"}]
    return []


def _download_github_archive(owner: str, repo_name: str, ref: str, destination: Path, token: Optional[str] = None) -> None:
    url = f"https://api.github.com/repos/{owner}/{repo_name}/zipball/{ref}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    response = requests.get(url, headers=headers, timeout=120)
    response.raise_for_status()

    archive = zipfile.ZipFile(BytesIO(response.content))
    archive.extractall(destination)

    # GitHub archive wraps files under a single top-level directory.
    top_dirs = [p for p in destination.iterdir() if p.is_dir()]
    if len(top_dirs) == 1:
        wrapped_root = top_dirs[0]
        for child in wrapped_root.iterdir():
            shutil.move(str(child), str(destination / child.name))
        wrapped_root.rmdir()


def _write_architecture_doc(
    tenant_id: str,
    repository: ConnectedRepository,
    snapshot: RepoSnapshot,
    runtime_summary: Dict[str, Any],
    static_summary: Dict[str, Any],
) -> Dict[str, str]:
    unique_key = uuid.uuid4().hex[:12]
    docs_root = _workspace_root() / tenant_id / repository.id / "architecture_docs"
    docs_root.mkdir(parents=True, exist_ok=True)

    md_path = docs_root / f"architecture_{unique_key}.md"
    json_path = docs_root / f"architecture_{unique_key}.json"

    md_content = "\n".join(
        [
            f"# architecture_{unique_key}",
            "",
            "## Repository Context",
            f"- repository: {repository.full_name}",
            f"- branch: {snapshot.branch}",
            f"- commit_sha: {snapshot.commit_sha or 'unknown'}",
            "",
            "## Runtime Telemetry (Preferred when available)",
            f"- total_spans: {runtime_summary['total_spans']}",
            f"- detected_services: {', '.join(runtime_summary['services']) if runtime_summary['services'] else 'none'}",
            "",
            "## Static Repository Analysis (Mandatory)",
            f"- file_count: {static_summary['file_count']}",
            f"- top_file_types: {static_summary['top_file_types']}",
            f"- dependency_files: {static_summary['dependency_files']}",
            f"- database_signals: {static_summary['database_signals']}",
            "",
            "## Fusion Summary",
            "- This document fuses runtime telemetry and static repository analysis.",
            "- Runtime is preferred when available; static analysis remains mandatory.",
        ]
    )

    json_content = {
        "metadata": {
            "unique_key": unique_key,
            "created_at": datetime.utcnow().isoformat(),
            "tenant_id": tenant_id,
            "repository_id": repository.id,
            "snapshot_id": snapshot.id,
        },
        "repository": {
            "full_name": repository.full_name,
            "branch": snapshot.branch,
            "commit_sha": snapshot.commit_sha,
        },
        "runtime": runtime_summary,
        "static": static_summary,
        "fusion": {
            "runtime_preferred": True,
            "static_mandatory": True,
        },
    }

    md_path.write_text(md_content, encoding="utf-8")
    json_path.write_text(json.dumps(json_content, indent=2), encoding="utf-8")

    return {
        "unique_key": unique_key,
        "markdown_path": str(md_path),
        "json_path": str(json_path),
    }


def _build_2d_architecture_graph(
    repository: ConnectedRepository,
    snapshot: RepoSnapshot,
    runtime_summary: Dict[str, Any],
    static_summary: Dict[str, Any],
    strict_deep: bool = True,
) -> Dict[str, Any]:
    """Build a JSON-first 2D system design flow payload from saved analysis context.

    Output is architecture-centric (runtime flow + core infrastructure) rather than
    file-name-centric, so frontend can render a real system design diagram.
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    dependency_files = [str(item).lower() for item in (static_summary.get("dependency_files", []) or [])]
    dependency_hints = [str(item).lower() for item in (static_summary.get("dependency_hints", []) or [])]
    db_signals = static_summary.get("database_signals", []) or []
    runtime_services = runtime_summary.get("services", []) or []
    repo_label = _humanize_component(repository.repo_name or repository.full_name.split("/")[-1])
    snapshot_path = Path(snapshot.snapshot_path)
    file_count = int(static_summary.get("file_count", 0) or 0)
    auto_deep = file_count >= int(settings.SYSTEM_ARCH_DEEP_GRAPH_FILE_THRESHOLD)
    deep_mode = bool(strict_deep or auto_deep)
    service_limit = int(settings.SYSTEM_ARCH_DEEP_GRAPH_SERVICE_LIMIT if deep_mode else settings.SYSTEM_ARCH_GRAPH_SERVICE_LIMIT)
    static_service_candidates = _derive_static_service_candidates(snapshot_path, limit=service_limit)

    def add_node(node_id: str, label: str, layer: str, kind: str, meta: Optional[Dict[str, Any]] = None) -> None:
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "layer": layer,
                "kind": kind,
                "meta": meta or {},
            }
        )

    def add_edge(source: str, target: str, edge_type: str, reason: str) -> None:
        edges.append(
            {
                "id": f"edge_{source}_{target}",
                "source": source,
                "target": target,
                "type": edge_type,
                "meta": {"reason": reason},
            }
        )

    add_node(
        "client",
        f"{repo_label} Client Applications",
        "client",
        "entrypoint",
        {"repository": repository.full_name},
    )
    add_node("edge", "Edge / Load Balancer", "edge", "ingress")
    add_node(
        "api_gateway",
        f"{repo_label} API Gateway",
        "application",
        "gateway",
        {
            "branch": snapshot.branch,
            "commit_sha": snapshot.commit_sha,
            "file_count": static_summary.get("file_count", 0),
        },
    )
    add_edge("client", "edge", "https", "entry_traffic")
    add_edge("edge", "api_gateway", "routes", "edge_routing")

    service_ids: List[str] = []
    seen_service_ids = set()
    for service_name in runtime_services[:service_limit]:
        base_id = f"svc_{_slugify_component(service_name)}"
        service_id = base_id
        suffix = 2
        while service_id in seen_service_ids:
            service_id = f"{base_id}_{suffix}"
            suffix += 1
        seen_service_ids.add(service_id)
        service_ids.append(service_id)
        add_node(service_id, _humanize_component(service_name), "application", "runtime_service", {"telemetry_detected": True})
        add_edge("api_gateway", service_id, "calls", "runtime_telemetry_service")

    if not service_ids:
        for candidate in static_service_candidates:
            service_id = f"svc_static_{candidate['id']}"
            service_ids.append(service_id)
            add_node(
                service_id,
                f"{candidate['label']} Service",
                "application",
                "static_service",
                {
                    "inferred_from": "source_structure",
                    "sample_path": candidate["sample_path"],
                    "inference_score": candidate["score"],
                },
            )
            add_edge("api_gateway", service_id, "calls", "static_service_inference")

    if not service_ids:
        add_node("app_core", f"{repo_label} Core Service", "application", "app_service")
        add_edge("api_gateway", "app_core", "calls", "minimal_static_fallback")
        service_ids = ["app_core"]

    dependency_text = " ".join(dependency_files + dependency_hints)
    has_queue = any(marker in dependency_text for marker in ["kafka", "rabbit", "sqs", "celery", "pubsub", "eventbridge"])
    has_cache = any(marker in dependency_text for marker in ["redis", "memcache", "cachetools"])
    has_external = any(marker in dependency_text for marker in ["stripe", "twilio", "sendgrid", "httpx", "requests", "grpc", "boto3", "azure", "openai"])

    if has_queue:
        add_node("async_queue", "Async Queue / Event Bus", "async", "queue")
        add_node("worker_pool", "Worker Pool", "async", "workers")
        for sid in service_ids:
            add_edge(sid, "async_queue", "publishes", "async_boundary")
        add_edge("async_queue", "worker_pool", "consumes", "event_processing")

    if has_cache:
        add_node("cache_layer", "Cache Layer", "data", "cache")
        for sid in service_ids:
            add_edge(sid, "cache_layer", "reads_writes", "latency_optimization")

    data_store_candidates = _derive_data_store_candidates(snapshot_path, dependency_text, db_signals, limit=4)
    for index, data_store in enumerate(data_store_candidates):
        node_id = data_store["id"] if index == 0 else f"{data_store['id']}_{index + 1}"
        add_node(
            node_id,
            data_store["label"],
            "data",
            "database",
            {"database_signal_count": len(db_signals)},
        )
        for sid in service_ids:
            add_edge(sid, node_id, "queries", "persistence_flow")

    if has_external:
        add_node("external_integrations", "External Integrations", "external", "external_api")
        for sid in service_ids[: (8 if deep_mode else 4)]:
            add_edge(sid, "external_integrations", "calls", "third_party_integration")

    if deep_mode:
        add_node("ci_cd_pipeline", "CI/CD Pipeline", "external", "delivery_pipeline")
        add_node("policy_guardrails", "Policy Guardrails", "external", "security_policy")
        add_edge("repo_context", "ci_cd_pipeline", "triggers", "repo_to_delivery")
        add_edge("ci_cd_pipeline", "api_gateway", "deploys", "delivery_to_runtime")
        add_edge("policy_guardrails", "api_gateway", "enforces", "policy_enforcement")

    add_node(
        "repo_context",
        f"{repo_label} Repository Context",
        "source",
        "repository",
        {
            "dependency_manifest_count": len(dependency_files),
            "dependency_hint_count": len(dependency_hints),
            "database_signal_count": len(db_signals),
            "inferred_service_count": len(static_service_candidates),
            "graph_mode": "ultra" if deep_mode else "standard",
            "auto_deep": auto_deep,
            "strict_deep": strict_deep,
        },
    )
    add_edge("repo_context", "api_gateway", "implements", "source_to_runtime_mapping")
    for sid in service_ids[:8]:
        add_edge("repo_context", sid, "defines", "repo_structure_mapping")

    return {
        "version": "1.0",
        "generated_at": datetime.utcnow().isoformat(),
        "repository": {
            "id": repository.id,
            "full_name": repository.full_name,
            "snapshot_id": snapshot.id,
        },
        "graph_mode": "ultra" if deep_mode else "standard",
        "graph_mode_meta": {
            "strict_deep": strict_deep,
            "auto_deep": auto_deep,
            "file_count": file_count,
            "file_threshold": int(settings.SYSTEM_ARCH_DEEP_GRAPH_FILE_THRESHOLD),
            "service_limit": service_limit,
        },
        "nodes": nodes,
        "edges": edges,
        "layout_hint": "2d-layered",
        "layers": ["client", "edge", "source", "application", "async", "data", "external"],
    }


def _load_doc_context(doc: ArchitectureDocument) -> Dict[str, Any]:
    try:
        payload = json.loads(Path(doc.json_path).read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return {
        "runtime": payload.get("runtime", {}),
        "static": payload.get("static", {}),
        "metadata": payload.get("metadata", {}),
    }


def _strip_code_fences(content: str) -> str:
    text = (content or "").strip()
    if text.startswith("```json"):
        return text.split("```json", 1)[1].rsplit("```", 1)[0].strip()
    if text.startswith("```"):
        return text.split("```", 1)[1].rsplit("```", 1)[0].strip()
    return text


def _estimate_lowest_monthly_cost_signal_based(
    profile: str,
    dependency_names: List[str],
    runtime_services: List[str],
    major_changes: List[str],
) -> Dict[str, Any]:
    profile = str(profile or "balanced").lower()
    dep_text = " ".join(dependency_names).lower()
    changes_text = " ".join(major_changes).lower()

    def env_float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    unit_usd = env_float("SYSTEM_ARCH_COST_UNIT_USD", 3.8)
    profile_multiplier = {
        "cost": env_float("SYSTEM_ARCH_COST_PROFILE_COST", 0.9),
        "scalability": env_float("SYSTEM_ARCH_COST_PROFILE_SCALABILITY", 1.08),
        "performance": env_float("SYSTEM_ARCH_COST_PROFILE_PERFORMANCE", 1.18),
        "balanced": env_float("SYSTEM_ARCH_COST_PROFILE_BALANCED", 1.0),
    }.get(profile, 1.0)

    service_count = max(1, len(set(runtime_services)))
    dependency_count = max(1, len(set(dependency_names)))
    change_count = max(1, len(major_changes))

    cache_signal = 1 if any(token in dep_text or token in changes_text for token in ["redis", "cache", "caching", "memcache"]) else 0
    queue_signal = 1 if any(token in dep_text or token in changes_text for token in ["kafka", "rabbit", "sqs", "queue", "async", "event", "celery"]) else 0
    edge_signal = 1 if any(token in dep_text or token in changes_text for token in ["cdn", "edge", "latency", "performance", "global"]) else 0
    external_signal = 1 if any(token in dep_text for token in ["openai", "twilio", "stripe", "sendgrid", "anthropic"]) else 0

    def to_monthly(units: float, factor: float) -> float:
        return round(max(0.0, units) * unit_usd * factor * profile_multiplier, 2)

    compute_units = 1.2 + (service_count * 0.2) + (change_count * 0.08)
    database_units = 0.9 + (service_count * 0.08) + (dependency_count * 0.02)
    storage_units = 0.4 + (dependency_count * 0.03) + (service_count * 0.02)
    observability_units = 0.5 + (service_count * 0.06) + (change_count * 0.04)
    cache_units = (0.7 + (service_count * 0.05)) * cache_signal
    queue_units = (0.8 + (service_count * 0.07)) * queue_signal
    edge_units = (0.6 + (service_count * 0.04)) * edge_signal
    external_units = (0.5 + (dependency_count * 0.03)) * external_signal
    fanout_units = max(0, service_count - 2) * 0.14

    components = [
        {"component": "Compute baseline", "monthly_usd": to_monthly(compute_units, 2.2)},
        {"component": "Managed database baseline", "monthly_usd": to_monthly(database_units, 1.9)},
        {"component": "Storage and backup baseline", "monthly_usd": to_monthly(storage_units, 1.2)},
        {"component": "Observability baseline", "monthly_usd": to_monthly(observability_units, 1.35)},
    ]
    if cache_signal:
        components.append({"component": "Cache workload", "monthly_usd": to_monthly(cache_units, 1.8)})
    if queue_signal:
        components.append({"component": "Queue and async workload", "monthly_usd": to_monthly(queue_units, 1.7)})
    if edge_signal:
        components.append({"component": "Edge and network workload", "monthly_usd": to_monthly(edge_units, 1.45)})
    if external_signal:
        components.append({"component": "External API allowance", "monthly_usd": to_monthly(external_units, 1.1)})
    if fanout_units > 0:
        components.append({"component": "Service fan-out overhead", "monthly_usd": to_monthly(fanout_units, 1.0)})

    total = round(sum(item["monthly_usd"] for item in components), 2)
    return {
        "provider": "azure",
        "region": "central-india",
        "currency": "USD",
        "pricing_model": "signal-based-dynamic",
        "reasoning_engine": "langgraph-signals",
        "estimate_confidence": 0.62,
        "assumptions": [
            "Estimation is for minimum monthly production baseline in Central India.",
            "No committed-use discounts or enterprise contracts are applied.",
            "Workload is derived from architecture change signals and service topology.",
        ],
        "references": [
            {
                "source": "runtime_services",
                "evidence_count": service_count,
                "evidence": runtime_services[:15],
            },
            {
                "source": "dependency_names",
                "evidence_count": dependency_count,
                "evidence": dependency_names[:20],
            },
            {
                "source": "major_changes",
                "evidence_count": change_count,
                "evidence": major_changes[:10],
            },
        ],
        "pricing_inputs": {
            "unit_usd": unit_usd,
            "profile_multiplier": profile_multiplier,
            "service_count": service_count,
            "dependency_count": dependency_count,
            "change_count": change_count,
            "signals": {
                "cache": bool(cache_signal),
                "queue": bool(queue_signal),
                "edge": bool(edge_signal),
                "external": bool(external_signal),
            },
        },
        "components": components,
        "lowest_cost_per_month_usd": total,
    }


def _estimate_lowest_monthly_cost_with_azure_openai(
    profile: str,
    dependency_details: List[Dict[str, Any]],
    runtime_services: List[str],
    major_changes: List[str],
    baseline_estimate: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
        return None

    deployment = settings.AZURE_OPENAI_DEPLOYMENT_GPT5 or settings.AZURE_OPENAI_DEPLOYMENT
    prompt_payload = {
        "profile": profile,
        "region": "central-india",
        "currency": "USD",
        "runtime_services": runtime_services[:25],
        "major_changes": major_changes[:20],
        "dependency_versions": dependency_details[:20],
        "baseline_signal_estimate": {
            "lowest_cost_per_month_usd": baseline_estimate.get("lowest_cost_per_month_usd"),
            "components": baseline_estimate.get("components", []),
            "references": baseline_estimate.get("references", []),
        },
    }

    prompt = (
        "You are a cloud pricing analyst for Azure architecture planning. "
        "Use LangGraph-derived workflow signals and context to return the MOST PROBABLE monthly estimate. "
        "Return JSON only with keys: lowest_cost_per_month_usd (number), estimate_confidence (0-1), "
        "components (array of {component, monthly_usd, reason}), assumptions (string array), "
        "references (array of {source, evidence}).\n\n"
        f"Pricing Context: {json.dumps(prompt_payload)[:14000]}"
    )

    url = (
        f"{settings.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/"
        f"{deployment}/chat/completions?api-version={settings.AZURE_OPENAI_API_VERSION}"
    )
    payload = {
        "messages": [
            {"role": "system", "content": "You are precise and return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": min(settings.AZURE_OPENAI_MAX_TOKENS, 3000),
    }

    response = requests.post(
        url,
        headers={"api-key": settings.AZURE_OPENAI_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if not response.ok:
        fallback_payload = {
            "messages": payload["messages"],
            "temperature": 0.2,
            "max_tokens": 2200,
        }
        response = requests.post(
            url,
            headers={"api-key": settings.AZURE_OPENAI_API_KEY, "Content-Type": "application/json"},
            json=fallback_payload,
            timeout=60,
        )

    if not response.ok:
        return None

    try:
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_code_fences(content))
    except Exception:
        return None

    try:
        probable_total = float(parsed.get("lowest_cost_per_month_usd"))
    except Exception:
        return None
    if probable_total <= 0:
        return None

    raw_components = parsed.get("components") or []
    components: List[Dict[str, Any]] = []
    for item in raw_components:
        if not isinstance(item, dict):
            continue
        try:
            monthly = round(float(item.get("monthly_usd", 0)), 2)
        except Exception:
            continue
        if monthly < 0:
            continue
        components.append(
            {
                "component": str(item.get("component") or "Unspecified component"),
                "monthly_usd": monthly,
                "reason": str(item.get("reason") or "AI-inferred from architecture context"),
            }
        )

    if not components:
        for item in baseline_estimate.get("components", []):
            components.append(
                {
                    "component": item.get("component"),
                    "monthly_usd": item.get("monthly_usd"),
                    "reason": "Derived from deterministic signal baseline",
                }
            )

    confidence = parsed.get("estimate_confidence")
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.68
    confidence = max(0.0, min(1.0, confidence))

    ai_references = parsed.get("references") if isinstance(parsed.get("references"), list) else []
    normalized_refs = [
        {
            "source": str(item.get("source") if isinstance(item, dict) else "ai"),
            "evidence": item.get("evidence") if isinstance(item, dict) else str(item),
        }
        for item in ai_references[:20]
    ]
    normalized_refs.append(
        {
            "source": "baseline_signal_estimate",
            "evidence": {
                "lowest_cost_per_month_usd": baseline_estimate.get("lowest_cost_per_month_usd"),
                "pricing_model": baseline_estimate.get("pricing_model"),
            },
        }
    )

    assumptions = parsed.get("assumptions") if isinstance(parsed.get("assumptions"), list) else []

    return {
        "provider": "azure",
        "region": "central-india",
        "currency": "USD",
        "pricing_model": "langgraph-azure-openai-probable",
        "reasoning_engine": "langgraph+azure-openai",
        "estimate_confidence": round(confidence, 3),
        "assumptions": [str(item) for item in assumptions[:20]]
        or ["AI-derived probable monthly estimate based on architecture context and baseline signals."],
        "references": normalized_refs,
        "pricing_context": {
            "target_profile": profile,
            "runtime_service_count": len(runtime_services),
            "dependency_count": len(dependency_details),
            "major_change_count": len(major_changes),
        },
        "baseline_signal_estimate_usd": baseline_estimate.get("lowest_cost_per_month_usd"),
        "components": components,
        "lowest_cost_per_month_usd": round(probable_total, 2),
    }


def _estimate_lowest_monthly_cost(
    profile: str,
    dependency_details: List[Dict[str, Any]],
    runtime_services: List[str],
    major_changes: List[str],
) -> Dict[str, Any]:
    dependency_names = [str(item.get("name") or "").strip().lower() for item in dependency_details if str(item.get("name") or "").strip()]
    baseline = _estimate_lowest_monthly_cost_signal_based(
        profile=profile,
        dependency_names=dependency_names,
        runtime_services=runtime_services,
        major_changes=major_changes,
    )
    ai_configured = bool(settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_API_KEY)
    ai_estimate = _estimate_lowest_monthly_cost_with_azure_openai(
        profile=profile,
        dependency_details=dependency_details,
        runtime_services=runtime_services,
        major_changes=major_changes,
        baseline_estimate=baseline,
    )
    if ai_estimate:
        return ai_estimate

    baseline_copy = dict(baseline)
    baseline_copy["ai_pricing_attempted"] = ai_configured
    if ai_configured:
        baseline_copy["pricing_model"] = "signal-based-dynamic-fallback"
    return baseline_copy


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _estimate_scalability_users(profile: str, service_count: int, dependency_count: int, major_change_count: int) -> int:
    base = 800 + (service_count * 1400) + (dependency_count * 110) + (major_change_count * 450)
    multiplier = {
        "cost": 0.85,
        "balanced": 1.0,
        "scalability": 1.4,
        "performance": 1.2,
    }.get(str(profile or "balanced").lower(), 1.0)
    return int(max(500, round(base * multiplier)))


def _estimate_complexity_score(profile: str, service_count: int, dependency_count: int, major_change_count: int) -> int:
    base = 2.0 + (service_count * 0.08) + (dependency_count * 0.03) + (major_change_count * 0.9)
    profile_delta = {
        "cost": -0.4,
        "balanced": 0.0,
        "scalability": 1.0,
        "performance": 1.2,
    }.get(str(profile or "balanced").lower(), 0.2)
    return int(max(1, min(10, round(base + profile_delta))))


def _estimate_reliability_score(profile: str, service_count: int, major_change_count: int) -> int:
    base = 62 + min(18, service_count * 2)
    profile_adjust = {
        "cost": -3,
        "balanced": 0,
        "scalability": 3,
        "performance": 2,
    }.get(str(profile or "balanced").lower(), 0)
    change_penalty = min(8, major_change_count * 2)
    return int(max(45, min(96, base + profile_adjust - change_penalty + 4)))


def _estimate_implementation_weeks(profile: str, complexity_score: int, major_change_count: int) -> int:
    base = max(1, round((complexity_score * 0.9) + (major_change_count * 0.8)))
    profile_boost = {
        "cost": 0,
        "balanced": 1,
        "scalability": 2,
        "performance": 2,
    }.get(str(profile or "balanced").lower(), 1)
    return int(max(1, base + profile_boost))


def _estimate_performance_gain_percent(profile: str, major_change_count: int) -> int:
    profile_base = {
        "cost": 10,
        "balanced": 16,
        "scalability": 22,
        "performance": 30,
    }.get(str(profile or "balanced").lower(), 14)
    return int(max(5, min(75, profile_base + (major_change_count * 3))))


def _build_comparison_decision_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "recommended_workflow": None,
            "cheapest_workflow": None,
            "highest_scalability_workflow": None,
            "highest_reliability_workflow": None,
            "rationale": "No workflows available for comparison.",
        }

    cheapest = min(rows, key=lambda item: _to_float(item.get("estimated_cost_usd"), 10**9))
    highest_scalability = max(rows, key=lambda item: _to_float(item.get("scalability_users_estimate"), 0.0))
    highest_reliability = max(rows, key=lambda item: _to_float(item.get("reliability_score"), 0.0))
    max_scalability = max(1.0, _to_float(highest_scalability.get("scalability_users_estimate"), 1.0))

    def score(row: Dict[str, Any]) -> float:
        reliability = _to_float(row.get("reliability_score"), 0.0)
        scalability_ratio = _to_float(row.get("scalability_users_estimate"), 0.0) / max_scalability
        cost = _to_float(row.get("estimated_cost_usd"), 0.0)
        complexity = _to_float(row.get("complexity_score"), 10.0)
        risk = _to_float(row.get("operational_risk_score"), 10.0)
        performance_gain = _to_float(row.get("performance_gain_percent"), 0.0)
        return (
            reliability * 0.32
            + scalability_ratio * 28.0
            + max(0.0, 18.0 - (cost * 0.12))
            + max(0.0, 10.0 - complexity)
            + max(0.0, 10.0 - risk)
            + (performance_gain * 0.18)
        )

    recommended = max(rows, key=score)

    return {
        "recommended_workflow": recommended.get("workflow_name"),
        "cheapest_workflow": cheapest.get("workflow_name"),
        "highest_scalability_workflow": highest_scalability.get("workflow_name"),
        "highest_reliability_workflow": highest_reliability.get("workflow_name"),
        "rationale": (
            f"Recommended {recommended.get('workflow_name')} based on weighted tradeoff across "
            "cost, scalability, reliability, risk, and expected performance gain."
        ),
    }


def _enhance_workflow_comparison_matrix_with_azure_openai(matrix: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
        return matrix

    deployment = settings.AZURE_OPENAI_DEPLOYMENT_GPT5 or settings.AZURE_OPENAI_DEPLOYMENT
    prompt_payload = {
        "matrix_rows": [
            {
                "workflow_name": row.get("workflow_name"),
                "workflow_type": row.get("workflow_type"),
                "estimated_cost_usd": row.get("estimated_cost_usd"),
                "complexity_score": row.get("complexity_score"),
                "scalability_users_estimate": row.get("scalability_users_estimate"),
                "reliability_score": row.get("reliability_score"),
                "implementation_effort_weeks": row.get("implementation_effort_weeks"),
                "operational_risk_score": row.get("operational_risk_score"),
                "performance_gain_percent": row.get("performance_gain_percent"),
                "reference_count": len(row.get("references") or []),
            }
            for row in (matrix.get("rows") or [])
        ],
        "decision_summary": matrix.get("decision_summary") or {},
    }
    prompt = (
        "You are a principal architecture reviewer. Refine this workflow comparison matrix using the provided context and references. "
        "Return JSON only with keys: decision_summary and rows. "
        "decision_summary keys: recommended_workflow, cheapest_workflow, highest_scalability_workflow, "
        "highest_reliability_workflow, rationale. "
        "rows is array with keys: workflow_name, rationale, reference_notes (string array).\n\n"
        f"Comparison Matrix Context: {json.dumps(prompt_payload)[:12000]}"
    )

    url = (
        f"{settings.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/"
        f"{deployment}/chat/completions?api-version={settings.AZURE_OPENAI_API_VERSION}"
    )
    payload = {
        "messages": [
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": min(settings.AZURE_OPENAI_MAX_TOKENS, 2500),
    }

    response = requests.post(
        url,
        headers={"api-key": settings.AZURE_OPENAI_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=50,
    )
    if not response.ok:
        fallback_payload = {
            "messages": payload["messages"],
            "temperature": 0.2,
            "max_tokens": 1600,
        }
        response = requests.post(
            url,
            headers={"api-key": settings.AZURE_OPENAI_API_KEY, "Content-Type": "application/json"},
            json=fallback_payload,
            timeout=50,
        )
    if not response.ok:
        return matrix

    try:
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_code_fences(content))
    except Exception:
        return matrix

    decision_summary = parsed.get("decision_summary") if isinstance(parsed.get("decision_summary"), dict) else None
    row_notes = parsed.get("rows") if isinstance(parsed.get("rows"), list) else []
    note_by_name = {}
    for row in row_notes:
        if not isinstance(row, dict):
            continue
        name = str(row.get("workflow_name") or "").strip()
        if not name:
            continue
        note_by_name[name] = row

    updated_rows: List[Dict[str, Any]] = []
    for row in matrix.get("rows") or []:
        enriched = dict(row)
        notes = note_by_name.get(str(row.get("workflow_name") or ""), {})
        if notes:
            rationale = str(notes.get("rationale") or "").strip()
            if rationale:
                enriched["ai_rationale"] = rationale
            ref_notes = notes.get("reference_notes") if isinstance(notes.get("reference_notes"), list) else []
            if ref_notes:
                merged_refs = list(enriched.get("references") or [])
                merged_refs.extend(
                    {
                        "source": "azure_openai_matrix_reasoning",
                        "evidence": str(item),
                    }
                    for item in ref_notes[:10]
                )
                enriched["references"] = merged_refs
        updated_rows.append(enriched)

    updated_matrix = dict(matrix)
    updated_matrix["rows"] = updated_rows
    if decision_summary:
        updated_matrix["decision_summary"] = {
            "recommended_workflow": decision_summary.get("recommended_workflow") or matrix.get("decision_summary", {}).get("recommended_workflow"),
            "cheapest_workflow": decision_summary.get("cheapest_workflow") or matrix.get("decision_summary", {}).get("cheapest_workflow"),
            "highest_scalability_workflow": decision_summary.get("highest_scalability_workflow") or matrix.get("decision_summary", {}).get("highest_scalability_workflow"),
            "highest_reliability_workflow": decision_summary.get("highest_reliability_workflow") or matrix.get("decision_summary", {}).get("highest_reliability_workflow"),
            "rationale": decision_summary.get("rationale") or matrix.get("decision_summary", {}).get("rationale"),
        }
    updated_matrix["reasoning_engine"] = "langgraph+azure-openai-comparison"
    updated_matrix["ai_matrix_enhanced"] = True
    return updated_matrix


def _build_workflow_comparison_matrix(
    document_id: str,
    context: Dict[str, Any],
    variants: List[Dict[str, Any]],
) -> Dict[str, Any]:
    static_summary = context.get("static", {}) or {}
    runtime_summary = context.get("runtime", {}) or {}
    runtime_services = [str(item) for item in (runtime_summary.get("services") or [])]

    dependency_inventory = list(static_summary.get("dependency_inventory") or [])
    if not dependency_inventory:
        dependency_inventory = [
            {
                "name": name,
                "version": "unspecified",
                "source": "static_hints",
                "scope": "runtime",
            }
            for name in (static_summary.get("dependency_hints") or [])
            if _is_plausible_dependency_name(str(name))
        ]

    original_changes = [
        "Current architecture baseline as observed from runtime and static signals",
        "No migration changes applied",
    ]
    original_cost = _estimate_lowest_monthly_cost_signal_based(
        profile="balanced",
        dependency_names=[str(dep.get("name") or "") for dep in dependency_inventory],
        runtime_services=runtime_services,
        major_changes=original_changes,
    )

    service_count = len(runtime_services)
    dependency_count = len(dependency_inventory)
    original_complexity = _estimate_complexity_score("balanced", service_count, dependency_count, 0)
    original_scalability = _estimate_scalability_users("balanced", service_count, dependency_count, 0)
    original_reliability = _estimate_reliability_score("balanced", service_count, 0)

    rows: List[Dict[str, Any]] = [
        {
            "workflow_id": "original-baseline",
            "workflow_name": "Original Architecture (Current Baseline)",
            "workflow_type": "original",
            "target_profile": "balanced",
            "estimated_cost_usd": round(float(original_cost.get("lowest_cost_per_month_usd") or 0.0), 2),
            "complexity_score": original_complexity,
            "scalability_users_estimate": original_scalability,
            "reliability_score": original_reliability,
            "implementation_effort_weeks": 0,
            "operational_risk_score": max(1, min(10, original_complexity - 1)),
            "performance_gain_percent": 0,
            "benefit_summary": [
                "Represents existing production baseline without migration risk.",
                "Reference point for generated workflow tradeoff analysis.",
            ],
            "references": list(original_cost.get("references") or []) + [
                {"source": "runtime_services", "evidence": runtime_services[:15]},
                {"source": "dependency_inventory", "evidence": [dep.get("name") for dep in dependency_inventory[:15]]},
            ],
            "assumptions": list(original_cost.get("assumptions") or []),
            "row_order": 0,
        }
    ]

    for index, variant_row in enumerate(variants, start=1):
        variant_payload = variant_row.get("variant") or {}
        profile = str(variant_payload.get("target_profile") or "balanced").lower()
        major_changes = [str(item) for item in (variant_payload.get("major_changes") or [])]
        dependency_versions = list(variant_payload.get("dependency_versions_used") or [])

        monthly_cost_estimate = variant_payload.get("monthly_cost_estimate") or {}
        if not monthly_cost_estimate:
            monthly_cost_estimate = _estimate_lowest_monthly_cost_signal_based(
                profile=profile,
                dependency_names=[str(dep.get("name") or "") for dep in dependency_versions],
                runtime_services=runtime_services,
                major_changes=major_changes,
            )

        estimated_cost = _to_float(
            variant_payload.get("lowest_cost_per_month_usd")
            or monthly_cost_estimate.get("lowest_cost_per_month_usd"),
            _to_float(monthly_cost_estimate.get("lowest_cost_per_month_usd"), 0.0),
        )
        complexity = _estimate_complexity_score(profile, service_count, len(dependency_versions), len(major_changes))
        scalability = _estimate_scalability_users(profile, service_count, len(dependency_versions), len(major_changes))
        reliability = _estimate_reliability_score(profile, service_count, len(major_changes))
        implementation_weeks = _estimate_implementation_weeks(profile, complexity, len(major_changes))
        operational_risk = int(max(1, min(10, round((complexity * 0.65) + (implementation_weeks * 0.15) - (reliability / 22.0)))))
        performance_gain = _estimate_performance_gain_percent(profile, len(major_changes))

        rows.append(
            {
                "workflow_id": variant_row.get("id") or f"variant-{index}",
                "workflow_name": variant_row.get("title") or f"Generated Variant {index}",
                "workflow_type": "generated",
                "target_profile": profile,
                "estimated_cost_usd": round(estimated_cost, 2),
                "complexity_score": complexity,
                "scalability_users_estimate": scalability,
                "reliability_score": reliability,
                "implementation_effort_weeks": implementation_weeks,
                "operational_risk_score": operational_risk,
                "performance_gain_percent": performance_gain,
                "benefit_summary": list(variant_payload.get("benefits_to_use") or [])[:4],
                "references": list(monthly_cost_estimate.get("references") or []) + [
                    {"source": "major_changes", "evidence": major_changes[:10]},
                    {
                        "source": "dependency_versions_used",
                        "evidence": [
                            {
                                "name": dep.get("name"),
                                "version": dep.get("version"),
                                "source": dep.get("source"),
                            }
                            for dep in dependency_versions[:10]
                        ],
                    },
                    {"source": "workflow_reasoning", "evidence": variant_payload.get("workflow_reasoning") or {}},
                ],
                "assumptions": list(monthly_cost_estimate.get("assumptions") or []),
                "row_order": index,
            }
        )

    matrix = {
        "document_id": document_id,
        "generated_at": datetime.utcnow().isoformat(),
        "reasoning_engine": "langgraph-deep-comparison",
        "factors": [
            {"key": "estimated_cost_usd", "label": "Estimated Cost (USD/month)", "unit": "USD", "direction": "lower_is_better"},
            {"key": "complexity_score", "label": "Complexity", "unit": "1-10", "direction": "lower_is_better"},
            {"key": "scalability_users_estimate", "label": "Scalability Users", "unit": "users", "direction": "higher_is_better"},
            {"key": "reliability_score", "label": "Reliability", "unit": "0-100", "direction": "higher_is_better"},
            {"key": "implementation_effort_weeks", "label": "Implementation Effort", "unit": "weeks", "direction": "lower_is_better"},
            {"key": "operational_risk_score", "label": "Operational Risk", "unit": "1-10", "direction": "lower_is_better"},
            {"key": "performance_gain_percent", "label": "Performance Gain", "unit": "%", "direction": "higher_is_better"},
        ],
        "rows": rows,
        "decision_summary": _build_comparison_decision_summary(rows),
    }
    return _enhance_workflow_comparison_matrix_with_azure_openai(matrix)


def _enrich_variant_with_workflow_reference(
    variant: Dict[str, Any],
    static_summary: Dict[str, Any],
    runtime_summary: Dict[str, Any],
) -> Dict[str, Any]:
    enriched = dict(variant)
    profile = str(enriched.get("target_profile") or "balanced").lower()
    major_changes = [str(item) for item in (enriched.get("major_changes") or [])]
    change_tokens = set(
        token
        for change in major_changes
        for token in re.split(r"[^a-z0-9]+", change.lower())
        if len(token) >= 4
    )

    inventory = list(static_summary.get("dependency_inventory") or [])
    if not inventory:
        inventory = [
            {
                "name": name,
                "version": "unspecified",
                "source": "static_hints",
                "scope": "runtime",
            }
            for name in (static_summary.get("dependency_hints") or [])
            if _is_plausible_dependency_name(str(name))
        ]

    def dep_score(dep: Dict[str, Any]) -> int:
        name = str(dep.get("name") or "").lower()
        source = str(dep.get("source") or "").lower()
        score = 1
        if any(token in name for token in change_tokens):
            score += 5
        if profile == "performance" and any(k in name for k in ["redis", "grpc", "uvloop", "numpy", "fastapi", "next"]):
            score += 4
        if profile == "scalability" and any(k in name for k in ["kafka", "rabbit", "celery", "queue", "postgres", "mongo"]):
            score += 4
        if profile == "cost" and any(k in name for k in ["sqlite", "cache", "requests", "httpx"]):
            score += 4
        if "requirements" in source or "package.json" in source or "pyproject" in source:
            score += 2
        return score

    ranked = sorted(inventory, key=dep_score, reverse=True)
    selected_dependencies: List[Dict[str, Any]] = []
    seen_names = set()
    for dep in ranked:
        name = str(dep.get("name") or "").strip().lower()
        if not _is_plausible_dependency_name(name) or name in seen_names:
            continue
        seen_names.add(name)
        selected_dependencies.append(
            {
                "name": name,
                "version": str(dep.get("version") or "unspecified"),
                "source": str(dep.get("source") or "unknown"),
                "scope": str(dep.get("scope") or "runtime"),
                "rationale": "selected_by_reasoning",
            }
        )
        if len(selected_dependencies) >= 10:
            break

    recommended = _build_contextual_dependency_recommendations(
        profile=profile,
        major_changes=major_changes,
        static_summary=static_summary,
        runtime_summary=runtime_summary,
    )
    for rec in recommended:
        name = str(rec.get("name") or "").strip().lower()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        selected_dependencies.append(
            {
                "name": name,
                "version": "unspecified",
                "source": str(rec.get("source") or "langgraph_dependency_reasoning"),
                "scope": "runtime",
                "rationale": str(rec.get("rationale") or "recommended_by_contextual_reasoning"),
            }
        )
        if len(selected_dependencies) >= 10:
            break

    if not selected_dependencies:
        for item in ["fastapi", "sqlalchemy", "pydantic", "redis", "httpx", "requests"]:
            selected_dependencies.append(
                {
                    "name": item,
                    "version": "unspecified",
                    "source": "langgraph_dependency_reasoning",
                    "scope": "runtime",
                    "rationale": "baseline_fallback_for_architecture_generation",
                }
            )

    validated_dependencies: List[Dict[str, Any]] = []
    for dep in selected_dependencies[:10]:
        name = str(dep.get("name") or "").strip().lower()
        if not _is_plausible_dependency_name(name):
            continue
        validation = _validate_dependency_version(
            name=name,
            version=str(dep.get("version") or "unspecified"),
            source=str(dep.get("source") or ""),
        )
        validated_dependencies.append(
            {
                "name": name,
                "version": validation.get("resolved_version") or "unspecified",
                "latest_version": validation.get("latest_version"),
                "ecosystem": validation.get("ecosystem"),
                "version_validation_status": validation.get("validation_status"),
                "version_validation_source": validation.get("validation_source"),
                "registry_url": validation.get("registry_url"),
                "source": str(dep.get("source") or "unknown"),
                "scope": str(dep.get("scope") or "runtime"),
                "rationale": str(dep.get("rationale") or "selected_by_reasoning"),
            }
        )

    if validated_dependencies:
        selected_dependencies = validated_dependencies

    profile_benefits = {
        "cost": [
            "Minimizes monthly infrastructure baseline while preserving core reliability.",
            "Reduces over-provisioned services and duplicated components.",
            "Uses shared platform primitives for lower operational overhead.",
        ],
        "scalability": [
            "Improves horizontal scaling and traffic burst absorption.",
            "Introduces async boundaries to isolate high-load execution paths.",
            "Reduces bottlenecks through service decomposition and queueing.",
        ],
        "performance": [
            "Optimizes latency-critical paths and response consistency.",
            "Improves cache hit probability and reduces synchronous chain depth.",
            "Adds architecture patterns for better throughput under peak load.",
        ],
    }

    benefits = list(profile_benefits.get(profile, profile_benefits["scalability"]))
    for item in major_changes[:3]:
        benefits.append(f"Implements: {item}")

    monthly_cost_estimate = _estimate_lowest_monthly_cost(
        profile=profile,
        dependency_details=selected_dependencies,
        runtime_services=list(runtime_summary.get("services") or []),
        major_changes=major_changes,
    )

    enriched["dependency_versions_used"] = selected_dependencies
    enriched["benefits_to_use"] = benefits[:8]
    enriched["monthly_cost_estimate"] = monthly_cost_estimate
    enriched["lowest_cost_per_month_usd"] = monthly_cost_estimate["lowest_cost_per_month_usd"]
    enriched["workflow_reasoning"] = {
        "reasoning_engine": "langgraph-dependency-reasoner+registry-validation",
        "signals": {
            "target_profile": profile,
            "major_changes_count": len(major_changes),
            "dependency_candidates": len(inventory),
            "contextual_dependency_hints": len(static_summary.get("contextual_dependency_hints") or []),
            "runtime_service_count": len(runtime_summary.get("services") or []),
            "recommended_candidates": len(recommended),
        },
    }
    return enriched


def _enrich_variants_for_workflow_references(
    variants: List[Dict[str, Any]],
    static_summary: Dict[str, Any],
    runtime_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [
        _enrich_variant_with_workflow_reference(variant, static_summary, runtime_summary)
        for variant in variants
    ]


def _build_variants_payload(weights: Dict[str, Any]) -> List[Dict[str, Any]]:
    normalized = weights["normalized"]

    return [
        {
            "variant_index": 1,
            "title": "Cost-Efficient Architecture",
            "target_profile": "cost",
            "weights": normalized,
            "major_changes": [
                "Increase shared infrastructure utilization",
                "Introduce aggressive caching for expensive paths",
                "Consolidate low-traffic services",
            ],
        },
        {
            "variant_index": 2,
            "title": "Scalability-Oriented Architecture",
            "target_profile": "scalability",
            "weights": normalized,
            "major_changes": [
                "Isolate high-traffic domains into separate services",
                "Add queue-based async boundaries",
                "Apply read/write scaling strategy",
            ],
        },
        {
            "variant_index": 3,
            "title": "Performance-Optimized Architecture",
            "target_profile": "performance",
            "weights": normalized,
            "major_changes": [
                "Optimize critical latency paths",
                "Introduce low-latency data access patterns",
                "Reduce synchronous service chaining",
            ],
        },
    ]


def _generate_variants_with_gpt5(doc: ArchitectureDocument, weights: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
        raise RuntimeError("Azure OpenAI not configured")

    deployment = settings.AZURE_OPENAI_DEPLOYMENT_GPT5 or settings.AZURE_OPENAI_DEPLOYMENT
    prompt_context = {}
    try:
        prompt_context = json.loads(Path(doc.json_path).read_text(encoding="utf-8"))
    except Exception:
        prompt_context = {
            "unique_key": doc.unique_key,
            "runtime_enriched": doc.runtime_enriched,
        }

    prompt = (
        "Generate exactly 3 architecture variants in JSON array format. "
        "Each item must contain: variant_index (1-3), title, target_profile, major_changes (string array). "
        "Use weights as optimization priorities and keep responses implementation-focused.\n\n"
        f"Weights: {json.dumps(weights['normalized'])}\n"
        f"Architecture context: {json.dumps(prompt_context)[:12000]}"
    )

    url = (
        f"{settings.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/"
        f"{deployment}/chat/completions?api-version={settings.AZURE_OPENAI_API_VERSION}"
    )
    payload = {
        "messages": [
            {"role": "system", "content": "You are a software architecture expert. Return JSON only."},
            {"role": "user", "content": prompt},
        ],
        # GPT-5 Azure deployments can require max_completion_tokens and default temperature.
        "max_completion_tokens": settings.AZURE_OPENAI_MAX_TOKENS,
    }
    response = requests.post(
        url,
        headers={"api-key": settings.AZURE_OPENAI_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=90,
    )
    if not response.ok:
        # Compatibility fallback for non-GPT-5 deployments.
        fallback_payload = {
            "messages": payload["messages"],
            "temperature": 0.3,
            "max_tokens": settings.AZURE_OPENAI_MAX_TOKENS,
        }
        fallback = requests.post(
            url,
            headers={"api-key": settings.AZURE_OPENAI_API_KEY, "Content-Type": "application/json"},
            json=fallback_payload,
            timeout=90,
        )
        response = fallback
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"].strip()

    if content.startswith("```json"):
        content = content.split("```json", 1)[1].rsplit("```", 1)[0].strip()
    elif content.startswith("```"):
        content = content.split("```", 1)[1].rsplit("```", 1)[0].strip()

    parsed = json.loads(content)
    if not isinstance(parsed, list) or len(parsed) < 3:
        raise RuntimeError("GPT-5 response does not contain 3 variants")

    variants: List[Dict[str, Any]] = []
    for i, item in enumerate(parsed[:3], start=1):
        if not isinstance(item, dict):
            continue
        variants.append(
            {
                "variant_index": i,
                "title": item.get("title") or f"Architecture Variant {i}",
                "target_profile": item.get("target_profile") or ["cost", "scalability", "performance"][i - 1],
                "weights": weights["normalized"],
                "major_changes": item.get("major_changes") if isinstance(item.get("major_changes"), list) else ["Refactor architecture based on variant objective"],
            }
        )

    if len(variants) < 3:
        raise RuntimeError("Failed to parse 3 valid variants from GPT-5 response")
    return variants


def _store_variants(db: Session, tenant_id: str, architecture_document_id: str, variants: List[Dict[str, Any]]) -> List[ArchitectureVariant]:
    created: List[ArchitectureVariant] = []
    for variant in variants:
        row = ArchitectureVariant(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            architecture_document_id=architecture_document_id,
            variant_index=variant["variant_index"],
            title=variant["title"],
            weights_json=json.dumps(variant["weights"]),
            variant_json=json.dumps(variant),
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return created


def _notify_architecture_generation_status(
    db: Session,
    tenant_id: str,
    doc: ArchitectureDocument,
    status: str,
    variant_ids: Optional[List[str]] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    smtp_status = NotificationService.get_smtp_runtime_status()
    user = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.is_active == True)
        .order_by(User.created_at.asc())
        .first()
    )
    if not user or not user.email:
        return {
            "status": "disabled",
            "message": "Email notification disabled: no active user email found.",
            "configured": bool(smtp_status.get("configured")),
            "recipient": None,
            "sent": False,
            "attempted": False,
        }

    repo = db.query(ConnectedRepository).filter(ConnectedRepository.id == doc.repository_id).first()
    repo_name = repo.full_name if repo and repo.full_name else doc.repository_id

    if status == "completed":
        summary = (
            f"Architecture analysis and variant generation completed successfully. "
            f"Generated variants: {len(variant_ids or [])}."
        )
    else:
        summary = f"Architecture generation failed. {error_message or 'Please retry from the dashboard.'}"

    delivery = NotificationService.send_system_architecture_status(
        to_email=user.email,
        repository_name=repo_name,
        architecture_document_key=doc.unique_key,
        status=status,
        summary=summary,
    )

    if delivery.get("sent"):
        return {
            "status": "sent",
            "message": f"Email notification sent to {user.email}.",
            "configured": bool(delivery.get("configured", False)),
            "recipient": user.email,
            "sent": True,
            "attempted": True,
        }

    reason = delivery.get("reason") or "Email delivery skipped."
    if delivery.get("configured"):
        return {
            "status": "failed",
            "message": f"Email notification could not be sent: {reason}",
            "configured": True,
            "recipient": user.email,
            "sent": False,
            "attempted": bool(delivery.get("attempted")),
        }

    return {
        "status": "disabled",
        "message": "Email notification disabled: SMTP is not configured.",
        "configured": False,
        "recipient": user.email,
        "sent": False,
        "attempted": False,
    }


def _build_architecture_email_preview(db: Session, tenant_id: str) -> Dict[str, Any]:
    smtp_status = NotificationService.get_smtp_runtime_status()
    user = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.is_active == True)
        .order_by(User.created_at.asc())
        .first()
    )

    if not smtp_status.get("configured"):
        return {
            "status": "disabled",
            "message": "Email notification disabled: SMTP is not configured.",
            "configured": False,
            "recipient": user.email if user and user.email else None,
            "sent": False,
            "attempted": False,
        }

    if smtp_status.get("disabled_reason"):
        return {
            "status": "disabled",
            "message": f"Email notification disabled: {smtp_status.get('disabled_reason')}",
            "configured": True,
            "recipient": user.email if user and user.email else None,
            "sent": False,
            "attempted": False,
        }

    if not user or not user.email:
        return {
            "status": "disabled",
            "message": "Email notification disabled: no active user email found.",
            "configured": True,
            "recipient": None,
            "sent": False,
            "attempted": False,
        }

    return {
        "status": "will_notify",
        "message": f"You will get an email notification at {user.email} when generation completes.",
        "configured": True,
        "recipient": user.email,
        "sent": False,
        "attempted": False,
    }


def _generate_variants_background(job_id: str, db_factory, tenant_id: str, architecture_document_id: str, weights: Dict[str, Any]) -> None:
    _VARIANT_JOBS[job_id] = {"status": "in_progress", "created_at": datetime.utcnow().isoformat()}
    db = db_factory()
    try:
        doc = (
            db.query(ArchitectureDocument)
            .filter(ArchitectureDocument.id == architecture_document_id, ArchitectureDocument.tenant_id == tenant_id)
            .first()
        )
        if not doc:
            raise RuntimeError("Architecture document not found for variant generation")

        context = _load_doc_context(doc)
        static_summary = context.get("static", {})
        runtime_summary = context.get("runtime", {})

        variants: List[Dict[str, Any]]
        try:
            variants = _generate_variants_with_gpt5(doc, weights)
        except Exception:
            if settings.SYSTEM_ARCH_ALLOW_SYNC_FALLBACK:
                variants = _build_variants_payload(weights)
            else:
                raise

        variants = _enrich_variants_for_workflow_references(variants, static_summary, runtime_summary)

        rows = _store_variants(db, tenant_id, architecture_document_id, variants)
        email_notification = _notify_architecture_generation_status(
            db=db,
            tenant_id=tenant_id,
            doc=doc,
            status="completed",
            variant_ids=[row.id for row in rows],
        )
        _VARIANT_JOBS[job_id] = {
            "status": "completed",
            "variant_ids": [row.id for row in rows],
            "email_notification": email_notification,
            "created_at": _VARIANT_JOBS[job_id]["created_at"],
            "completed_at": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        email_notification = None
        try:
            if 'doc' in locals() and doc:
                email_notification = _notify_architecture_generation_status(
                    db=db,
                    tenant_id=tenant_id,
                    doc=doc,
                    status="failed",
                    error_message=str(exc),
                )
        except Exception:
            pass
        _VARIANT_JOBS[job_id] = {
            "status": "failed",
            "error": str(exc),
            "email_notification": email_notification,
            "created_at": _VARIANT_JOBS[job_id]["created_at"],
            "completed_at": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()


def _variant_reports_root(tenant_id: str, repository_id: str) -> Path:
    root = _workspace_root() / tenant_id / repository_id / "workflow_reports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_graph_payload_for_document(
    db: Session,
    tenant_id: str,
    doc: ArchitectureDocument,
    repo: ConnectedRepository,
    snapshot: RepoSnapshot,
) -> Dict[str, Any]:
    graph_path = Path(doc.json_path).with_name(f"architecture_graph_{doc.unique_key}.json")
    if graph_path.exists():
        try:
            return json.loads(graph_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    context = _load_doc_context(doc)
    static_summary = context.get("static") or {}
    runtime_summary = context.get("runtime") or {}

    snapshot_path = Path(snapshot.snapshot_path)
    if snapshot_path.exists():
        try:
            static_summary = _extract_static_summary(snapshot_path)
        except Exception:
            pass

    if not runtime_summary:
        runtime_summary = _count_runtime_signals(db, tenant_id)

    graph_payload = _build_2d_architecture_graph(
        repo,
        snapshot,
        runtime_summary,
        static_summary,
        strict_deep=True,
    )

    try:
        graph_path.write_text(json.dumps(graph_payload, indent=2), encoding="utf-8")
    except Exception:
        pass
    return graph_payload


def _execute_variant_report_generation(db_factory, report_id: str) -> None:
    db = db_factory()
    try:
        report = db.query(ArchitectureVariantReport).filter(ArchitectureVariantReport.id == report_id).first()
        if not report:
            return

        existing_summary = json.loads(report.summary_json) if report.summary_json else {}
        include_official_references = bool(existing_summary.get("include_official_references", True))

        report.status = "in_progress"
        report.started_at = datetime.utcnow()
        report.error_message = None
        db.commit()

        variant = (
            db.query(ArchitectureVariant)
            .filter(
                ArchitectureVariant.id == report.architecture_variant_id,
                ArchitectureVariant.tenant_id == report.tenant_id,
            )
            .first()
        )
        doc = (
            db.query(ArchitectureDocument)
            .filter(
                ArchitectureDocument.id == report.architecture_document_id,
                ArchitectureDocument.tenant_id == report.tenant_id,
            )
            .first()
        )
        repo = (
            db.query(ConnectedRepository)
            .filter(
                ConnectedRepository.id == report.repository_id,
                ConnectedRepository.tenant_id == report.tenant_id,
            )
            .first()
        )
        snapshot = (
            db.query(RepoSnapshot)
            .filter(
                RepoSnapshot.id == report.snapshot_id,
                RepoSnapshot.tenant_id == report.tenant_id,
            )
            .first()
        )

        if not variant or not doc or not repo or not snapshot:
            raise RuntimeError("Missing architecture context for workflow report generation")

        variant_payload = json.loads(variant.variant_json)
        context = _load_doc_context(doc)
        graph_payload = _resolve_graph_payload_for_document(db, report.tenant_id, doc, repo, snapshot)

        reports_root = _variant_reports_root(report.tenant_id, report.repository_id)
        artifact = generate_variant_report_artifacts(
            report_id=report.id,
            reports_root=reports_root,
            repository_full_name=repo.full_name,
            document_id=doc.id,
            variant_row_id=variant.id,
            variant_title=variant.title,
            variant_payload=variant_payload,
            architecture_context=context,
            graph_payload=graph_payload,
            include_official_references=include_official_references,
        )

        report.status = "completed"
        report.report_markdown_path = artifact["markdown_path"]
        report.report_pdf_path = artifact["pdf_path"]
        report.summary_json = json.dumps(
            {
                **(artifact.get("summary") or {}),
                "include_official_references": include_official_references,
            }
        )
        report.completed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        row = db.query(ArchitectureVariantReport).filter(ArchitectureVariantReport.id == report_id).first()
        if row:
            row.status = "failed"
            row.error_message = f"{exc}\n{traceback.format_exc(limit=4)}"
            row.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@router.get("/github/install-url")
def github_install_url(tenant_id: str = Depends(get_tenant_id_from_jwt)) -> Dict[str, str]:
    if settings.GITHUB_APP_SLUG:
        url = f"https://github.com/apps/{settings.GITHUB_APP_SLUG}/installations/new?state={tenant_id}"
    else:
        url = f"https://github.com/apps/installations/new?state={tenant_id}"
    return {"install_url": url, "mode": "github_app_installation"}


@router.post("/github/installations")
def upsert_installation(
    payload: GitHubInstallationUpsert,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    existing = (
        db.query(GitHubInstallation)
        .filter(
            GitHubInstallation.tenant_id == tenant_id,
            GitHubInstallation.github_installation_id == payload.github_installation_id,
        )
        .first()
    )

    if existing:
        existing.account_login = payload.account_login
        existing.account_type = payload.account_type
        db.commit()
        db.refresh(existing)
        return {"status": "updated", "installation_id": existing.id}

    row = GitHubInstallation(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        github_installation_id=payload.github_installation_id,
        account_login=payload.account_login,
        account_type=payload.account_type,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"status": "created", "installation_id": row.id}


@router.post("/github/installations/auto-link")
def auto_link_installation(
    installation_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if not GitHubAppService.is_configured():
        raise HTTPException(status_code=503, detail="GitHub App is not configured")

    try:
        metadata = GitHubAppService.get_installation_metadata(installation_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to resolve GitHub installation: {exc}")

    existing = (
        db.query(GitHubInstallation)
        .filter(
            GitHubInstallation.tenant_id == tenant_id,
            GitHubInstallation.github_installation_id == metadata["github_installation_id"],
        )
        .first()
    )

    if existing:
        existing.account_login = metadata["account_login"]
        existing.account_type = metadata["account_type"]
        db.commit()
        db.refresh(existing)
        return {
            "status": "updated",
            "installation_id": existing.id,
            "github_installation_id": existing.github_installation_id,
            "account_login": existing.account_login,
            "account_type": existing.account_type,
        }

    row = GitHubInstallation(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        github_installation_id=metadata["github_installation_id"],
        account_login=metadata["account_login"],
        account_type=metadata["account_type"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "status": "created",
        "installation_id": row.id,
        "github_installation_id": row.github_installation_id,
        "account_login": row.account_login,
        "account_type": row.account_type,
    }


@router.get("/github/installations")
def list_installations(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    rows = db.query(GitHubInstallation).filter(GitHubInstallation.tenant_id == tenant_id).all()
    return [
        {
            "id": row.id,
            "github_installation_id": row.github_installation_id,
            "account_login": row.account_login,
            "account_type": row.account_type,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/github/installations/{installation_id}/repositories")
def list_installation_repositories(
    installation_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    installation = (
        db.query(GitHubInstallation)
        .filter(GitHubInstallation.id == installation_id, GitHubInstallation.tenant_id == tenant_id)
        .first()
    )
    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    if not GitHubAppService.is_configured():
        return {
            "mode": "fallback",
            "configured": False,
            "repositories": [],
            "message": "GitHub App credentials are not configured yet",
        }

    try:
        repos = GitHubAppService.list_installation_repositories(installation.github_installation_id)
        return {"mode": "github_app", "configured": True, "repositories": repos}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch installation repositories: {exc}")


@router.post("/repositories/connect")
def connect_repository(
    payload: ConnectRepositoryRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    full_name = f"{payload.owner}/{payload.repo_name}"
    existing = (
        db.query(ConnectedRepository)
        .filter(
            ConnectedRepository.tenant_id == tenant_id,
            ConnectedRepository.full_name == full_name,
        )
        .first()
    )
    if existing:
        existing.default_branch = payload.default_branch
        existing.is_private = payload.is_private
        existing.is_monorepo = payload.is_monorepo
        existing.remote_url = payload.remote_url
        existing.local_repo_path = payload.local_repo_path
        existing.installation_id = payload.installation_id
        db.commit()
        db.refresh(existing)
        return {"status": "updated", "repository_id": existing.id, "full_name": full_name}

    repo = ConnectedRepository(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        installation_id=payload.installation_id,
        owner=payload.owner,
        repo_name=payload.repo_name,
        full_name=full_name,
        default_branch=payload.default_branch,
        is_private=payload.is_private,
        is_monorepo=payload.is_monorepo,
        remote_url=payload.remote_url,
        local_repo_path=payload.local_repo_path,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return {"status": "created", "repository_id": repo.id, "full_name": full_name}


@router.get("/repositories")
def list_repositories(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    repos = db.query(ConnectedRepository).filter(ConnectedRepository.tenant_id == tenant_id, ConnectedRepository.is_active == True).all()
    return [
        {
            "id": r.id,
            "full_name": r.full_name,
            "default_branch": r.default_branch,
            "is_private": r.is_private,
            "is_monorepo": r.is_monorepo,
            "installation_id": r.installation_id,
            "remote_url": r.remote_url,
            "local_repo_path": r.local_repo_path,
        }
        for r in repos
    ]


@router.get("/sdk-apps")
def list_sdk_apps(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return {
        "apps": _list_sdk_telemetry_apps(db, tenant_id),
        "default": None,
        "selection_behavior": "none_means_all_runtime_context",
    }


@router.post("/repositories/{repository_id}/snapshot")
def create_snapshot(
    repository_id: str,
    payload: SnapshotRequest,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    repo = (
        db.query(ConnectedRepository)
        .filter(ConnectedRepository.id == repository_id, ConnectedRepository.tenant_id == tenant_id)
        .first()
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    branch = repo.default_branch if payload.use_default_branch or not payload.branch else payload.branch
    snapshot_id = str(uuid.uuid4())
    snapshot_path = _workspace_root() / tenant_id / repository_id / "snapshots" / snapshot_id
    snapshot_path.mkdir(parents=True, exist_ok=True)

    status_value = "created"
    message = "Snapshot created"
    commit_sha = None

    if repo.local_repo_path:
        source = Path(repo.local_repo_path).resolve()
        if not source.exists() or not source.is_dir():
            raise HTTPException(status_code=400, detail="local_repo_path does not exist")

        # Prevent recursive copy when snapshot destination is nested inside source.
        if snapshot_path.resolve().is_relative_to(source):
            raise HTTPException(
                status_code=400,
                detail="local_repo_path cannot contain the snapshot workspace directory",
            )

        size_bytes = _repo_size_bytes(source)
        max_bytes = settings.MONOREPO_MAX_SIZE_MB * 1024 * 1024
        if size_bytes > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Monorepo exceeds max size {settings.MONOREPO_MAX_SIZE_MB} MB",
            )

        shutil.copytree(
            source,
            snapshot_path,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                ".git",
                "node_modules",
                ".next",
                "dist",
                "build",
                "__pycache__",
                "storage",
                "alpha_runs",
                "snapshots",
            ),
        )
        try:
            git_sha = subprocess.check_output(
                ["git", "-C", str(snapshot_path), "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=10,
                text=True,
            ).strip()
            commit_sha = git_sha
        except Exception:
            commit_sha = None
        snapshot_size = _repo_size_bytes(snapshot_path)
    elif repo.remote_url:
        try:
            clone_url = repo.remote_url
            installation = None
            token = None
            if repo.installation_id and GitHubAppService.is_configured():
                installation = (
                    db.query(GitHubInstallation)
                    .filter(GitHubInstallation.id == repo.installation_id, GitHubInstallation.tenant_id == tenant_id)
                    .first()
                )
            if installation:
                token = GitHubAppService.get_installation_access_token(installation.github_installation_id)
                if clone_url.startswith("https://"):
                    clone_url = clone_url.replace("https://", f"https://x-access-token:{token}@", 1)

            git_path = shutil.which("git")
            if git_path:
                clone_cmd = [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    branch,
                    clone_url,
                    str(snapshot_path),
                ]
                clone_result = subprocess.run(
                    clone_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                # Fallback: if requested branch clone fails, retry default branch.
                if clone_result.returncode != 0:
                    shutil.rmtree(snapshot_path, ignore_errors=True)
                    snapshot_path.mkdir(parents=True, exist_ok=True)
                    fallback_cmd = [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        clone_url,
                        str(snapshot_path),
                    ]
                    clone_result = subprocess.run(
                        fallback_cmd,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )

                if clone_result.returncode != 0:
                    raise RuntimeError(clone_result.stderr.strip() or clone_result.stdout.strip() or "git clone failed")

                status_value = "created"
                message = "Cloned from remote URL"
                try:
                    commit_sha = subprocess.check_output(
                        ["git", "-C", str(snapshot_path), "rev-parse", "HEAD"],
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                        text=True,
                    ).strip()
                except Exception:
                    commit_sha = None
                snapshot_size = _repo_size_bytes(snapshot_path)
            else:
                _download_github_archive(repo.owner, repo.repo_name, branch, snapshot_path, token)
                status_value = "created"
                message = "Downloaded snapshot archive from GitHub"
                commit_sha = None
                snapshot_size = _repo_size_bytes(snapshot_path)
        except Exception as exc:
            status_value = "failed"
            error_text = str(exc)
            if "x-access-token:" in error_text and "@" in error_text:
                start = error_text.find("x-access-token:")
                end = error_text.find("@", start)
                if start != -1 and end != -1:
                    error_text = error_text[:start] + "x-access-token:[REDACTED]" + error_text[end:]
            message = f"Remote clone failed: {error_text}"
            snapshot_size = 0
    else:
        status_value = "failed"
        message = "No local_repo_path or remote_url configured for repository"
        snapshot_size = 0

    row = RepoSnapshot(
        id=snapshot_id,
        tenant_id=tenant_id,
        repository_id=repository_id,
        branch=branch,
        commit_sha=commit_sha,
        snapshot_path=str(snapshot_path),
        snapshot_size_bytes=snapshot_size,
        status=status_value,
        message=message,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if row.status != "created":
        raise HTTPException(status_code=400, detail=row.message)

    return {
        "snapshot_id": row.id,
        "status": row.status,
        "message": row.message,
        "branch": row.branch,
        "commit_sha": row.commit_sha,
        "snapshot_size_bytes": row.snapshot_size_bytes,
    }


@router.post("/repositories/{repository_id}/analyze")
def analyze_repository(
    repository_id: str,
    payload: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    repo = (
        db.query(ConnectedRepository)
        .filter(ConnectedRepository.id == repository_id, ConnectedRepository.tenant_id == tenant_id)
        .first()
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    snapshot = (
        db.query(RepoSnapshot)
        .filter(
            RepoSnapshot.id == payload.snapshot_id,
            RepoSnapshot.repository_id == repository_id,
            RepoSnapshot.tenant_id == tenant_id,
        )
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    if snapshot.status != "created":
        raise HTTPException(status_code=400, detail=f"Snapshot is not ready: {snapshot.status}")

    snapshot_path = Path(snapshot.snapshot_path)
    if not snapshot_path.exists():
        raise HTTPException(status_code=400, detail="Snapshot path missing")

    static_summary = _extract_static_summary(snapshot_path)
    runtime_summary = _count_runtime_signals(
        db,
        tenant_id,
        payload.telemetry_project_id,
        payload.telemetry_service_name,
    )
    doc_files = _write_architecture_doc(tenant_id, repo, snapshot, runtime_summary, static_summary)

    doc = ArchitectureDocument(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        repository_id=repository_id,
        snapshot_id=snapshot.id,
        unique_key=doc_files["unique_key"],
        markdown_path=doc_files["markdown_path"],
        json_path=doc_files["json_path"],
        runtime_enriched=True,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    estimated_seconds = _estimate_variant_generation_seconds(static_summary, runtime_summary)
    mode = _resolve_generation_mode(payload.mode, estimated_seconds)
    weights = _normalize_weights(payload.cost_weight, payload.scalability_weight, payload.performance_weight)

    graph_payload = _build_2d_architecture_graph(repo, snapshot, runtime_summary, static_summary, strict_deep=True)
    graph_json_path = str(Path(doc_files["json_path"]).with_name(f"architecture_graph_{doc_files['unique_key']}.json"))
    Path(graph_json_path).write_text(json.dumps(graph_payload, indent=2), encoding="utf-8")

    if mode == "async":
        email_notification = _build_architecture_email_preview(db, tenant_id)
        job_id = str(uuid.uuid4())
        _VARIANT_JOBS[job_id] = {"status": "pending", "created_at": datetime.utcnow().isoformat()}
        background_tasks.add_task(
            _generate_variants_background,
            job_id,
            SessionLocal,
            tenant_id,
            doc.id,
            weights,
        )
        return {
            "architecture_document_id": doc.id,
            "unique_key": doc.unique_key,
            "generation_mode": "async",
            "job_id": job_id,
            "telemetry_project_id": payload.telemetry_project_id,
            "telemetry_service_name": payload.telemetry_service_name,
            "runtime_context_spans": runtime_summary.get("total_spans", 0),
            "weights": weights,
            "estimated_seconds": estimated_seconds,
            "sync_target_seconds": settings.SYSTEM_ARCH_SYNC_TARGET_SECONDS,
            "graph_json_path": graph_json_path,
            "email_notification": email_notification,
        }

    variants = _build_variants_payload(weights)
    try:
        variants = _generate_variants_with_gpt5(doc, weights)
    except Exception:
        if not settings.SYSTEM_ARCH_ALLOW_SYNC_FALLBACK:
            raise
    variants = _enrich_variants_for_workflow_references(variants, static_summary, runtime_summary)
    rows = _store_variants(db, tenant_id, doc.id, variants)
    email_notification = _notify_architecture_generation_status(
        db=db,
        tenant_id=tenant_id,
        doc=doc,
        status="completed",
        variant_ids=[r.id for r in rows],
    )
    return {
        "architecture_document_id": doc.id,
        "unique_key": doc.unique_key,
        "generation_mode": "sync",
        "variant_ids": [r.id for r in rows],
        "telemetry_project_id": payload.telemetry_project_id,
        "telemetry_service_name": payload.telemetry_service_name,
        "runtime_context_spans": runtime_summary.get("total_spans", 0),
        "weights": weights,
        "estimated_seconds": estimated_seconds,
        "sync_target_seconds": settings.SYSTEM_ARCH_SYNC_TARGET_SECONDS,
        "graph_json_path": graph_json_path,
        "email_notification": email_notification,
    }


@router.post("/generate-variants")
def generate_variants(
    payload: GenerateVariantsRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    doc = (
        db.query(ArchitectureDocument)
        .filter(ArchitectureDocument.id == payload.architecture_document_id, ArchitectureDocument.tenant_id == tenant_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Architecture document not found")

    context = _load_doc_context(doc)
    estimated_seconds = _estimate_variant_generation_seconds(context.get("static", {}), context.get("runtime", {}))
    mode = _resolve_generation_mode(payload.mode, estimated_seconds)
    weights = _normalize_weights(payload.cost_weight, payload.scalability_weight, payload.performance_weight)

    if mode == "async":
        email_notification = _build_architecture_email_preview(db, tenant_id)
        job_id = str(uuid.uuid4())
        _VARIANT_JOBS[job_id] = {"status": "pending", "created_at": datetime.utcnow().isoformat()}
        background_tasks.add_task(
            _generate_variants_background,
            job_id,
            SessionLocal,
            tenant_id,
            doc.id,
            weights,
        )
        return {
            "status": "queued",
            "job_id": job_id,
            "weights": weights,
            "generation_mode": "async",
            "estimated_seconds": estimated_seconds,
            "sync_target_seconds": settings.SYSTEM_ARCH_SYNC_TARGET_SECONDS,
            "email_notification": email_notification,
        }

    variants = _build_variants_payload(weights)
    try:
        variants = _generate_variants_with_gpt5(doc, weights)
    except Exception:
        if not settings.SYSTEM_ARCH_ALLOW_SYNC_FALLBACK:
            raise
    variants = _enrich_variants_for_workflow_references(
        variants,
        context.get("static", {}),
        context.get("runtime", {}),
    )
    rows = _store_variants(db, tenant_id, doc.id, variants)
    email_notification = _notify_architecture_generation_status(
        db=db,
        tenant_id=tenant_id,
        doc=doc,
        status="completed",
        variant_ids=[r.id for r in rows],
    )
    return {
        "status": "completed",
        "variant_ids": [r.id for r in rows],
        "weights": weights,
        "generation_mode": "sync",
        "estimated_seconds": estimated_seconds,
        "sync_target_seconds": settings.SYSTEM_ARCH_SYNC_TARGET_SECONDS,
        "email_notification": email_notification,
    }


@router.get("/jobs/{job_id}")
def get_generation_job(job_id: str) -> Dict[str, Any]:
    job = _VARIANT_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/documents")
def list_architecture_documents(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    rows = (
        db.query(ArchitectureDocument)
        .filter(ArchitectureDocument.tenant_id == tenant_id)
        .order_by(ArchitectureDocument.created_at.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "repository_id": row.repository_id,
            "snapshot_id": row.snapshot_id,
            "unique_key": row.unique_key,
            "markdown_path": row.markdown_path,
            "json_path": row.json_path,
            "runtime_enriched": row.runtime_enriched,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/variants")
def list_architecture_variants(
    architecture_document_id: Optional[str] = None,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = db.query(ArchitectureVariant).filter(ArchitectureVariant.tenant_id == tenant_id)
    if architecture_document_id:
        query = query.filter(ArchitectureVariant.architecture_document_id == architecture_document_id)
    rows = query.order_by(ArchitectureVariant.created_at.desc()).all()

    context_cache: Dict[str, Dict[str, Any]] = {}
    touched = False
    output: List[Dict[str, Any]] = []

    for row in rows:
        variant_payload = json.loads(row.variant_json)
        estimate = variant_payload.get("monthly_cost_estimate") or {}
        pricing_model = str(estimate.get("pricing_model") or "").strip().lower()
        has_cost = isinstance(variant_payload.get("lowest_cost_per_month_usd"), (int, float))
        references = estimate.get("references")
        assumptions = estimate.get("assumptions")
        dependency_versions = variant_payload.get("dependency_versions_used")

        has_references = isinstance(references, list) and len(references) > 0
        has_assumptions = isinstance(assumptions, list) and len(assumptions) > 0
        has_dependency_versions = isinstance(dependency_versions, list) and len(dependency_versions) > 0
        has_dependency_validation = False
        if has_dependency_versions:
            for dep in dependency_versions:
                if not isinstance(dep, dict):
                    continue
                version = str(dep.get("version") or "").strip().lower()
                latest = str(dep.get("latest_version") or "").strip().lower()
                validation_source = str(dep.get("version_validation_source") or "").strip().lower()
                if (version and version != "unspecified") or latest or validation_source:
                    has_dependency_validation = True
                    break
        needs_reference_backfill = (
            (not has_references)
            or (not has_assumptions)
            or (not has_dependency_versions)
            or (not has_dependency_validation)
        )

        # Backfill older variants that still carry hardcoded/legacy pricing structure.
        ai_pricing_enabled = bool(settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_API_KEY)
        if ai_pricing_enabled:
            needs_refresh = needs_reference_backfill or (not has_cost) or (pricing_model not in {"langgraph-azure-openai-probable", "signal-based-dynamic-fallback"})
        else:
            needs_refresh = needs_reference_backfill or (not has_cost) or (pricing_model not in {"signal-based-dynamic", "signal-based-dynamic-fallback", "langgraph-azure-openai-probable"})

        if needs_refresh:
            doc_id = row.architecture_document_id
            if doc_id not in context_cache:
                doc = (
                    db.query(ArchitectureDocument)
                    .filter(ArchitectureDocument.id == doc_id, ArchitectureDocument.tenant_id == tenant_id)
                    .first()
                )
                context_cache[doc_id] = _load_doc_context(doc) if doc else {"static": {}, "runtime": {}, "metadata": {}}

            doc_context = context_cache[doc_id]
            variant_payload = _enrich_variant_with_workflow_reference(
                variant_payload,
                doc_context.get("static", {}),
                doc_context.get("runtime", {}),
            )
            row.variant_json = json.dumps(variant_payload)
            touched = True

        output.append(
            {
                "id": row.id,
                "architecture_document_id": row.architecture_document_id,
                "variant_index": row.variant_index,
                "title": row.title,
                "weights": json.loads(row.weights_json),
                "variant": variant_payload,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )

    if touched:
        db.commit()

    return output


@router.post("/variants/{variant_id}/reports")
def generate_variant_report(
    variant_id: str,
    payload: GenerateVariantReportRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    variant = (
        db.query(ArchitectureVariant)
        .filter(ArchitectureVariant.id == variant_id, ArchitectureVariant.tenant_id == tenant_id)
        .first()
    )
    if not variant:
        raise HTTPException(status_code=404, detail="Architecture variant not found")

    doc = (
        db.query(ArchitectureDocument)
        .filter(ArchitectureDocument.id == variant.architecture_document_id, ArchitectureDocument.tenant_id == tenant_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=400, detail="Architecture document not found for variant")

    snapshot = (
        db.query(RepoSnapshot)
        .filter(RepoSnapshot.id == doc.snapshot_id, RepoSnapshot.tenant_id == tenant_id)
        .first()
    )
    repo = (
        db.query(ConnectedRepository)
        .filter(ConnectedRepository.id == doc.repository_id, ConnectedRepository.tenant_id == tenant_id)
        .first()
    )
    if not snapshot or not repo:
        raise HTTPException(status_code=400, detail="Variant context is incomplete")

    report_id = str(uuid.uuid4())
    row = ArchitectureVariantReport(
        id=report_id,
        tenant_id=tenant_id,
        architecture_variant_id=variant.id,
        architecture_document_id=doc.id,
        repository_id=repo.id,
        snapshot_id=snapshot.id,
        status="pending",
        summary_json=json.dumps(
            {
                "include_official_references": bool(payload.include_official_references),
                "requested_at": datetime.utcnow().isoformat(),
            }
        ),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    background_tasks.add_task(_execute_variant_report_generation, SessionLocal, row.id)

    return {
        "report_id": row.id,
        "status": row.status,
        "architecture_variant_id": row.architecture_variant_id,
        "architecture_document_id": row.architecture_document_id,
    }


@router.get("/variants/{variant_id}/reports")
def list_variant_reports(
    variant_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    rows = (
        db.query(ArchitectureVariantReport)
        .filter(
            ArchitectureVariantReport.tenant_id == tenant_id,
            ArchitectureVariantReport.architecture_variant_id == variant_id,
        )
        .order_by(ArchitectureVariantReport.created_at.desc())
        .all()
    )

    return [
        {
            "report_id": row.id,
            "status": row.status,
            "architecture_variant_id": row.architecture_variant_id,
            "report_pdf_path": row.report_pdf_path,
            "error_message": row.error_message,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/reports/{report_id}")
def get_variant_report(
    report_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    row = (
        db.query(ArchitectureVariantReport)
        .filter(ArchitectureVariantReport.id == report_id, ArchitectureVariantReport.tenant_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    summary = json.loads(row.summary_json) if row.summary_json else {}
    return {
        "report_id": row.id,
        "status": row.status,
        "architecture_variant_id": row.architecture_variant_id,
        "architecture_document_id": row.architecture_document_id,
        "report_markdown_path": row.report_markdown_path,
        "report_pdf_path": row.report_pdf_path,
        "summary": summary,
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/reports/{report_id}/download")
def download_variant_report(
    report_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
):
    row = (
        db.query(ArchitectureVariantReport)
        .filter(ArchitectureVariantReport.id == report_id, ArchitectureVariantReport.tenant_id == tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    if row.status != "completed" or not row.report_pdf_path:
        raise HTTPException(status_code=400, detail="Report PDF is not ready")

    report_path = Path(row.report_pdf_path)
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report PDF file missing")

    return FileResponse(
        path=str(report_path),
        media_type="application/pdf",
        filename=report_path.name,
    )


@router.get("/documents/{document_id}/comparison-matrix")
def get_workflow_comparison_matrix(
    document_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    doc = (
        db.query(ArchitectureDocument)
        .filter(ArchitectureDocument.id == document_id, ArchitectureDocument.tenant_id == tenant_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Architecture document not found")

    context = _load_doc_context(doc)
    rows = (
        db.query(ArchitectureVariant)
        .filter(
            ArchitectureVariant.tenant_id == tenant_id,
            ArchitectureVariant.architecture_document_id == document_id,
        )
        .order_by(ArchitectureVariant.variant_index.asc(), ArchitectureVariant.created_at.asc())
        .all()
    )

    variant_rows: List[Dict[str, Any]] = []
    touched = False
    for row in rows:
        payload = json.loads(row.variant_json)
        estimate = payload.get("monthly_cost_estimate") or {}
        references = estimate.get("references") if isinstance(estimate.get("references"), list) else []
        assumptions = estimate.get("assumptions") if isinstance(estimate.get("assumptions"), list) else []
        deps = payload.get("dependency_versions_used") if isinstance(payload.get("dependency_versions_used"), list) else []
        has_cost = isinstance(payload.get("lowest_cost_per_month_usd"), (int, float))
        has_dep_validation = False
        for dep in deps:
            if not isinstance(dep, dict):
                continue
            version = str(dep.get("version") or "").strip().lower()
            latest = str(dep.get("latest_version") or "").strip().lower()
            validation_source = str(dep.get("version_validation_source") or "").strip().lower()
            if (version and version != "unspecified") or latest or validation_source:
                has_dep_validation = True
                break

        if (not has_cost) or (not references) or (not assumptions) or (not deps) or (not has_dep_validation):
            payload = _enrich_variant_with_workflow_reference(
                payload,
                context.get("static", {}),
                context.get("runtime", {}),
            )
            row.variant_json = json.dumps(payload)
            touched = True

        variant_rows.append(
            {
                "id": row.id,
                "variant_index": row.variant_index,
                "title": row.title,
                "variant": payload,
            }
        )

    if touched:
        db.commit()

    return _build_workflow_comparison_matrix(document_id, context, variant_rows)


@router.get("/documents/{document_id}/graph-json")
def get_architecture_graph_json(
    document_id: str,
    strict_deep: bool = True,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    doc = (
        db.query(ArchitectureDocument)
        .filter(ArchitectureDocument.id == document_id, ArchitectureDocument.tenant_id == tenant_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Architecture document not found")

    graph_path = Path(doc.json_path).with_name(f"architecture_graph_{doc.unique_key}.json")

    repo = (
        db.query(ConnectedRepository)
        .filter(ConnectedRepository.id == doc.repository_id, ConnectedRepository.tenant_id == tenant_id)
        .first()
    )
    snapshot = (
        db.query(RepoSnapshot)
        .filter(RepoSnapshot.id == doc.snapshot_id, RepoSnapshot.tenant_id == tenant_id)
        .first()
    )

    if not repo or not snapshot:
        if graph_path.exists():
            try:
                return json.loads(graph_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to parse architecture graph JSON: {exc}")
        raise HTTPException(status_code=404, detail="Architecture graph JSON context not found")

    context = _load_doc_context(doc)
    static_summary = context.get("static") or {}
    runtime_summary = context.get("runtime") or {}

    snapshot_path = Path(snapshot.snapshot_path)
    if snapshot_path.exists():
        try:
            # Recompute static view so older docs receive repo-specific node names.
            static_summary = _extract_static_summary(snapshot_path)
        except Exception:
            pass

    if not runtime_summary:
        runtime_summary = _count_runtime_signals(db, tenant_id)

    graph_payload = _build_2d_architecture_graph(
        repo,
        snapshot,
        runtime_summary,
        static_summary,
        strict_deep=strict_deep,
    )
    try:
        graph_path.write_text(json.dumps(graph_payload, indent=2), encoding="utf-8")
    except Exception:
        # If persist fails, still return fresh graph payload.
        pass
    return graph_payload
