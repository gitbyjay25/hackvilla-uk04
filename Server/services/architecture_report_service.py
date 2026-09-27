from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.config import get_settings


settings = get_settings()


_PACKAGE_LOOKUP_CACHE: Dict[str, Dict[str, Any]] = {}


def _strip_code_fences(content: str) -> str:
    text = (content or "").strip()
    if text.startswith("```json"):
        return text.split("```json", 1)[1].rsplit("```", 1)[0].strip()
    if text.startswith("```"):
        return text.split("```", 1)[1].rsplit("```", 1)[0].strip()
    return text


def _version_sort_key(version: str) -> tuple:
    numeric = [int(part) for part in re.findall(r"\d+", str(version or ""))]
    if not numeric:
        return (0,)
    return tuple(numeric)


def _is_prerelease(version: str) -> bool:
    return bool(re.search(r"(?:a|b|rc|alpha|beta|pre|dev)", str(version or "").lower()))


def _normalize_current_version(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "unspecified"

    token = text.split(";", 1)[0].strip()
    token = token.split(",", 1)[0].strip()
    token = token.replace("^", "").replace("~", "")

    match = re.search(r"\d+(?:\.\d+){0,3}(?:[-+][a-z0-9\.]+)?", token, flags=re.IGNORECASE)
    return match.group(0) if match else token


def _detect_dependency_ecosystem(dep: Dict[str, Any]) -> str:
    source = str(dep.get("source") or "").lower()
    name = str(dep.get("name") or "")
    if source.endswith("package.json") or source.endswith("package-lock.json"):
        return "npm"
    if name.startswith("@"):
        return "npm"
    return "pypi"


def _fetch_latest_pypi(name: str) -> Dict[str, Any]:
    key = f"pypi:{name.lower()}"
    if key in _PACKAGE_LOOKUP_CACHE:
        return _PACKAGE_LOOKUP_CACHE[key]

    url = f"https://pypi.org/pypi/{name}/json"
    result: Dict[str, Any] = {
        "latest_version": None,
        "registry_url": url,
        "doc_url": None,
        "changelog_url": None,
        "summary": None,
        "references": [],
    }

    try:
        response = requests.get(url, timeout=20)
        if response.ok:
            payload = response.json()
            info = payload.get("info") or {}
            releases = payload.get("releases") or {}

            latest_version = str(info.get("version") or "").strip() or None
            if latest_version and _is_prerelease(latest_version):
                stable_versions = [v for v in releases.keys() if not _is_prerelease(v)]
                if stable_versions:
                    latest_version = sorted(stable_versions, key=_version_sort_key)[-1]

            project_urls = info.get("project_urls") or {}
            doc_url = project_urls.get("Documentation") or project_urls.get("Homepage") or info.get("home_page")
            changelog_url = (
                project_urls.get("Changelog")
                or project_urls.get("Release Notes")
                or project_urls.get("Releases")
            )

            result.update(
                {
                    "latest_version": latest_version,
                    "doc_url": doc_url,
                    "changelog_url": changelog_url,
                    "summary": info.get("summary"),
                }
            )
            result["references"] = [
                {"source": "pypi", "url": url, "evidence": f"Latest stable: {latest_version or 'unknown'}"},
            ]
            if doc_url:
                result["references"].append({"source": "official_docs", "url": doc_url, "evidence": "Documentation"})
            if changelog_url:
                result["references"].append({"source": "official_changelog", "url": changelog_url, "evidence": "Changelog"})
    except Exception:
        pass

    _PACKAGE_LOOKUP_CACHE[key] = result
    return result


def _fetch_latest_npm(name: str) -> Dict[str, Any]:
    key = f"npm:{name.lower()}"
    if key in _PACKAGE_LOOKUP_CACHE:
        return _PACKAGE_LOOKUP_CACHE[key]

    encoded_name = name.replace("/", "%2F")
    url = f"https://registry.npmjs.org/{encoded_name}"
    result: Dict[str, Any] = {
        "latest_version": None,
        "registry_url": f"https://www.npmjs.com/package/{name}",
        "doc_url": None,
        "changelog_url": None,
        "summary": None,
        "references": [],
    }

    try:
        response = requests.get(url, timeout=20)
        if response.ok:
            payload = response.json()
            latest_version = str(((payload.get("dist-tags") or {}).get("latest") or "")).strip() or None
            versions = payload.get("versions") or {}
            latest_meta = versions.get(latest_version or "", {}) if latest_version else {}

            repository = latest_meta.get("repository")
            if isinstance(repository, dict):
                repo_url = repository.get("url")
            else:
                repo_url = repository

            doc_url = latest_meta.get("homepage") or payload.get("homepage")
            changelog_url = f"{str(repo_url).replace('.git', '')}/releases" if repo_url else None

            result.update(
                {
                    "latest_version": latest_version,
                    "doc_url": doc_url,
                    "changelog_url": changelog_url,
                    "summary": payload.get("description"),
                }
            )
            result["references"] = [
                {
                    "source": "npm",
                    "url": result["registry_url"],
                    "evidence": f"Latest stable: {latest_version or 'unknown'}",
                }
            ]
            if doc_url:
                result["references"].append({"source": "official_docs", "url": doc_url, "evidence": "Documentation"})
            if changelog_url:
                result["references"].append({"source": "official_changelog", "url": changelog_url, "evidence": "Releases"})
    except Exception:
        pass

    _PACKAGE_LOOKUP_CACHE[key] = result
    return result


def _derive_dependency_reason(dep_name: str, major_changes: List[str], profile: str) -> str:
    text = f"{dep_name} {' '.join(major_changes).lower()}"
    if any(token in text for token in ["redis", "cache"]):
        return "Supports latency reduction and repeated-query optimization."
    if any(token in text for token in ["kafka", "rabbit", "queue", "celery", "sqs"]):
        return "Enables async boundaries and resilient workload distribution."
    if any(token in text for token in ["postgres", "mysql", "mongo", "dynamo", "database"]):
        return "Provides durable persistence and domain data consistency."
    if any(token in text for token in ["fastapi", "next", "react", "api"]):
        return "Aligns with the primary application/runtime framework."
    if profile == "performance":
        return "Chosen to maximize throughput and reduce tail latency."
    if profile == "scalability":
        return "Chosen for horizontal scaling and workload isolation."
    if profile == "cost":
        return "Chosen for operational simplicity and lower monthly baseline cost."
    return "Selected because it matches the generated architecture strategy."


def _build_implementation_steps(variant_title: str, major_changes: List[str], dependencies: List[Dict[str, Any]]) -> List[str]:
    steps = [
        f"Create an implementation branch for {variant_title} and lock baseline tests before refactor.",
        "Apply architecture boundary changes in small increments by service/domain to reduce blast radius.",
        "Upgrade or pin dependency versions based on the validated compatibility notes below.",
        "Implement infrastructure deltas (queue/cache/data path) before high-risk business logic rewrites.",
        "Add contract and regression tests for each changed API/service boundary.",
        "Run load and latency verification against the critical workflow path.",
        "Execute canary rollout and monitor traces/metrics before full promotion.",
        "Keep rollback package ready and preserve immutable snapshot for deterministic fallback.",
    ]

    for change in major_changes[:6]:
        steps.append(f"Implement major change: {change}")

    for dep in dependencies[:6]:
        if dep.get("update_status") == "update_available":
            steps.append(
                f"Validate upgrade path for {dep['name']} from {dep['current_version']} to {dep['latest_version']} in staging."
            )

    return steps[:18]


def _enhance_with_azure_openai(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
        return {}

    deployment = settings.AZURE_OPENAI_DEPLOYMENT_GPT5 or settings.AZURE_OPENAI_DEPLOYMENT
    prompt = (
        "You are a principal solutions architect. Enrich this report payload with deep guidance. "
        "Return JSON only with keys: executive_summary, dependency_guidance, implementation_guidance, "
        "risk_controls, architecture_narrative. Use concise professional language.\n\n"
        f"Report context: {json.dumps(payload)[:14000]}"
    )

    url = (
        f"{settings.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/"
        f"{deployment}/chat/completions?api-version={settings.AZURE_OPENAI_API_VERSION}"
    )
    req_payload = {
        "messages": [
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": min(settings.AZURE_OPENAI_MAX_TOKENS, 3200),
    }

    response = requests.post(
        url,
        headers={"api-key": settings.AZURE_OPENAI_API_KEY, "Content-Type": "application/json"},
        json=req_payload,
        timeout=60,
    )
    if not response.ok:
        return {}

    try:
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_code_fences(content))
    except Exception:
        return {}

    if not isinstance(parsed, dict):
        return {}
    return parsed


def _clip_text(value: Any, limit: int = 44) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    return text if len(text) <= limit else f"{text[: max(1, limit - 3)]}..."


def _build_graph_drawing(
    graph_payload: Dict[str, Any],
    *,
    width: float = 500,
    height: float = 305,
) -> Drawing:
    drawing = Drawing(width, height)
    nodes = list(graph_payload.get("nodes") or [])
    if not nodes:
        drawing.add(
            String(
                14,
                height - 24,
                "Architecture graph data is unavailable for this report.",
                fontSize=9,
                fillColor=colors.HexColor("#64748b"),
            )
        )
        return drawing

    layers = graph_payload.get("layers") or sorted({str(node.get("layer") or "application") for node in nodes})
    nodes_by_layer: Dict[str, List[Dict[str, Any]]] = {layer: [] for layer in layers}
    for node in nodes:
        layer = str(node.get("layer") or "application")
        if layer not in nodes_by_layer:
            nodes_by_layer[layer] = []
            layers.append(layer)
        nodes_by_layer[layer].append(node)

    lane_gap = 8
    lane_count = max(1, len(layers))
    lane_width = (width - (lane_gap * (lane_count + 1))) / lane_count
    lane_top = height - 28
    lane_bottom = 14
    lane_height = lane_top - lane_bottom
    lane_header_height = 20

    node_height = 30
    node_gap = 7
    body_height = lane_height - lane_header_height - 8
    max_nodes_per_lane = max(1, int((body_height + node_gap) // (node_height + node_gap)))

    kind_colors = {
        "entrypoint": colors.HexColor("#e0f2fe"),
        "ingress": colors.HexColor("#e0f2fe"),
        "gateway": colors.HexColor("#dbeafe"),
        "runtime_service": colors.HexColor("#e2e8f0"),
        "app_service": colors.HexColor("#e2e8f0"),
        "static_service": colors.HexColor("#e2e8f0"),
        "queue": colors.HexColor("#ede9fe"),
        "workers": colors.HexColor("#ede9fe"),
        "database": colors.HexColor("#dcfce7"),
        "cache": colors.HexColor("#fef9c3"),
        "external_api": colors.HexColor("#fee2e2"),
        "repository": colors.HexColor("#f8fafc"),
        "delivery_pipeline": colors.HexColor("#fce7f3"),
        "security_policy": colors.HexColor("#fce7f3"),
    }

    positions: Dict[str, Dict[str, float]] = {}
    for lane_index, layer in enumerate(layers):
        lane_x = lane_gap + lane_index * (lane_width + lane_gap)
        drawing.add(
            Rect(
                lane_x,
                lane_bottom,
                lane_width,
                lane_height,
                strokeColor=colors.HexColor("#cbd5e1"),
                fillColor=colors.HexColor("#f8fafc"),
                strokeWidth=0.8,
            )
        )
        drawing.add(
            Rect(
                lane_x,
                lane_top - lane_header_height,
                lane_width,
                lane_header_height,
                strokeColor=colors.HexColor("#cbd5e1"),
                fillColor=colors.HexColor("#e2e8f0"),
                strokeWidth=0.8,
            )
        )
        drawing.add(
            String(
                lane_x + 4,
                lane_top - lane_header_height + 7,
                _clip_text(layer.title(), 18),
                fontSize=7,
                fillColor=colors.HexColor("#0f172a"),
            )
        )

        lane_nodes = nodes_by_layer.get(layer, [])
        visible_nodes = lane_nodes[:max_nodes_per_lane]

        for node_index, node in enumerate(visible_nodes):
            node_id = str(node.get("id") or "")
            node_y = lane_top - lane_header_height - 8 - ((node_index + 1) * node_height) - (node_index * node_gap)
            fill_color = kind_colors.get(str(node.get("kind") or "").lower(), colors.HexColor("#e2e8f0"))

            drawing.add(
                Rect(
                    lane_x + 4,
                    node_y,
                    lane_width - 8,
                    node_height,
                    strokeColor=colors.HexColor("#94a3b8"),
                    fillColor=fill_color,
                    strokeWidth=0.8,
                )
            )
            drawing.add(
                String(
                    lane_x + 7,
                    node_y + 17,
                    _clip_text(node.get("label") or node.get("id") or "Node", 24),
                    fontSize=6.9,
                    fillColor=colors.HexColor("#0f172a"),
                )
            )

            kind_label = str(node.get("kind") or "").replace("_", " ").strip()
            if kind_label:
                drawing.add(
                    String(
                        lane_x + 7,
                        node_y + 7,
                        _clip_text(kind_label, 24),
                        fontSize=6,
                        fillColor=colors.HexColor("#475569"),
                    )
                )

            positions[node_id] = {
                "left": lane_x + 4,
                "right": lane_x + lane_width - 4,
                "center_x": lane_x + (lane_width / 2),
                "center_y": node_y + (node_height / 2),
            }

        hidden_count = max(0, len(lane_nodes) - len(visible_nodes))
        if hidden_count > 0:
            overflow_y = lane_bottom + 4
            drawing.add(
                Rect(
                    lane_x + 6,
                    overflow_y,
                    lane_width - 12,
                    12,
                    strokeColor=colors.HexColor("#cbd5e1"),
                    fillColor=colors.HexColor("#f1f5f9"),
                    strokeWidth=0.7,
                )
            )
            drawing.add(
                String(
                    lane_x + 9,
                    overflow_y + 4,
                    f"+{hidden_count} more nodes",
                    fontSize=6,
                    fillColor=colors.HexColor("#475569"),
                )
            )

    for edge in (graph_payload.get("edges") or [])[:120]:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in positions or target not in positions:
            continue

        source_pos = positions[source]
        target_pos = positions[target]
        sx = source_pos["right"] if source_pos["center_x"] <= target_pos["center_x"] else source_pos["left"]
        tx = target_pos["left"] if source_pos["center_x"] <= target_pos["center_x"] else target_pos["right"]
        sy = source_pos["center_y"]
        ty = target_pos["center_y"]

        drawing.add(
            Line(
                sx,
                sy,
                tx,
                ty,
                strokeColor=colors.HexColor("#94a3b8"),
                strokeWidth=0.65,
            )
        )
        drawing.add(Circle(tx, ty, 1.1, fillColor=colors.HexColor("#64748b"), strokeColor=colors.HexColor("#64748b")))

    return drawing


def _write_pdf_report(output_path: Path, payload: Dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontSize=22,
            leading=27,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(ParagraphStyle(name="Subtle", fontSize=8.8, textColor=colors.HexColor("#475569"), leading=12))
    styles.add(ParagraphStyle(name="Body", fontSize=10.2, leading=14.6, textColor=colors.HexColor("#1e293b")))
    styles.add(ParagraphStyle(name="Tiny", fontSize=8.1, leading=10.8, textColor=colors.HexColor("#334155")))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.55 * cm,
        rightMargin=1.55 * cm,
        topMargin=1.45 * cm,
        bottomMargin=1.35 * cm,
        title=payload.get("title") or "Architecture Workflow Report",
    )
    content_width = A4[0] - doc.leftMargin - doc.rightMargin

    dependencies = list(payload.get("dependencies") or [])
    major_changes = [str(item) for item in (payload.get("major_changes") or []) if str(item).strip()]
    graph_payload = payload.get("graph_payload") or {}
    graph_nodes = list(graph_payload.get("nodes") or [])
    graph_edges = list(graph_payload.get("edges") or [])
    graph_nodes_by_id = {str(node.get("id") or ""): node for node in graph_nodes}
    runtime_services = [
        node for node in graph_nodes if str(node.get("kind") or "") in {"runtime_service", "app_service", "static_service"}
    ]
    data_nodes = [node for node in graph_nodes if str(node.get("kind") or "") in {"database", "cache"}]
    updates_available = sum(1 for dep in dependencies if dep.get("update_status") == "update_available")

    story: List[Any] = []
    story.append(Paragraph(payload.get("title") or "Architecture Workflow Report", styles["ReportTitle"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(payload.get("subtitle") or "", styles["Subtle"]))
    story.append(Spacer(1, 12))

    summary_rows = [
        ["Repository", _clip_text(payload.get("repository") or "Unknown repository", 120)],
        ["Variant", _clip_text(payload.get("variant_title") or "Generated workflow", 120)],
        ["Target Profile", str(payload.get("target_profile") or "balanced").title()],
        ["Generated At (UTC)", _clip_text(payload.get("generated_at") or datetime.utcnow().isoformat(), 40)],
    ]
    summary_table = Table(summary_rows, colWidths=[content_width * 0.24, content_width * 0.76])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Executive Summary", styles["SectionTitle"]))
    story.append(Paragraph(payload.get("executive_summary") or "", styles["Body"]))
    story.append(Spacer(1, 10))

    if payload.get("architecture_narrative"):
        story.append(Paragraph("Architecture Narrative", styles["SectionTitle"]))
        story.append(Paragraph(str(payload.get("architecture_narrative")), styles["Body"]))
        story.append(Spacer(1, 8))

    story.append(Paragraph("Architecture Snapshot", styles["SectionTitle"]))
    snapshot_rows = [
        ["Graph Mode", str(payload.get("graph_summary", {}).get("graph_mode") or "standard")],
        ["Graph Nodes", str(len(graph_nodes))],
        ["Graph Edges", str(len(graph_edges))],
        ["Application Services", str(len(runtime_services))],
        ["Data Components", str(len(data_nodes))],
        ["Dependencies Assessed", str(len(dependencies))],
        ["Updates Available", str(updates_available)],
        ["Major Changes", str(len(major_changes))],
    ]
    snapshot_table = Table(snapshot_rows, colWidths=[content_width * 0.38, content_width * 0.62])
    snapshot_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(snapshot_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("System Architecture Diagram", styles["SectionTitle"]))
    story.append(_build_graph_drawing(graph_payload, width=min(content_width, 500), height=300))
    story.append(
        Paragraph(
            "Layered lanes show client, ingress, source, application, async, data, and external concerns; arrows represent primary interaction flow inferred from runtime and static analysis.",
            styles["Tiny"],
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("Critical Interaction Paths", styles["SectionTitle"]))
    flow_rows: List[List[Any]] = [["Source", "Target", "Flow Reason"]]
    for edge in graph_edges[:14]:
        source_id = str(edge.get("source") or "")
        target_id = str(edge.get("target") or "")
        source_label = _clip_text((graph_nodes_by_id.get(source_id) or {}).get("label") or source_id, 40)
        target_label = _clip_text((graph_nodes_by_id.get(target_id) or {}).get("label") or target_id, 40)
        flow_reason = _clip_text(((edge.get("meta") or {}).get("reason") or edge.get("type") or "inferred_flow"), 60)
        flow_rows.append(
            [
                Paragraph(html.escape(source_label), styles["Tiny"]),
                Paragraph(html.escape(target_label), styles["Tiny"]),
                Paragraph(html.escape(flow_reason), styles["Tiny"]),
            ]
        )

    flow_table = Table(
        flow_rows,
        repeatRows=1,
        colWidths=[content_width * 0.31, content_width * 0.31, content_width * 0.38],
    )
    flow_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(flow_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Major Architectural Changes", styles["SectionTitle"]))
    if major_changes:
        for idx, item in enumerate(major_changes[:16], start=1):
            story.append(Paragraph(f"{idx}. {html.escape(item)}", styles["Body"]))
    else:
        story.append(Paragraph("No major changes were provided for this variant.", styles["Body"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Dependency Intelligence", styles["SectionTitle"]))
    status_rank = {"update_available": 0, "version_not_pinned": 1, "unknown": 2, "up_to_date": 3}
    sorted_dependencies = sorted(
        dependencies,
        key=lambda dep: (status_rank.get(str(dep.get("update_status") or "unknown"), 4), str(dep.get("name") or "")),
    )

    dep_table_data: List[List[Any]] = [["Dependency", "Current", "Latest", "Status", "Architecture Reason"]]
    for dep in sorted_dependencies[:22]:
        dep_table_data.append(
            [
                Paragraph(html.escape(_clip_text(dep.get("name"), 34)), styles["Tiny"]),
                Paragraph(html.escape(_clip_text(dep.get("current_version") or "unspecified", 18)), styles["Tiny"]),
                Paragraph(html.escape(_clip_text(dep.get("latest_version") or "unknown", 18)), styles["Tiny"]),
                Paragraph(html.escape(_clip_text(dep.get("update_status") or "unknown", 18)), styles["Tiny"]),
                Paragraph(html.escape(_clip_text(dep.get("why_used") or "", 128)), styles["Tiny"]),
            ]
        )

    dep_table = Table(
        dep_table_data,
        repeatRows=1,
        colWidths=[content_width * 0.20, content_width * 0.13, content_width * 0.13, content_width * 0.14, content_width * 0.40],
    )
    dep_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(dep_table)
    story.append(
        Paragraph(
            f"Total dependencies analyzed: {len(dependencies)}; entries shown in table: {min(22, len(dependencies))}.",
            styles["Tiny"],
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("Implementation Guidance", styles["SectionTitle"]))
    for index, step in enumerate(payload.get("implementation_steps") or [], start=1):
        story.append(Paragraph(f"{index}. {html.escape(str(step))}", styles["Body"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Risk Controls", styles["SectionTitle"]))
    for index, risk in enumerate(payload.get("risk_controls") or [], start=1):
        story.append(Paragraph(f"{index}. {html.escape(str(risk))}", styles["Body"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("References", styles["SectionTitle"]))
    for ref in (payload.get("references") or [])[:40]:
        source = ref.get("source") or "reference"
        evidence = ref.get("evidence") or ""
        url = ref.get("url") or ""
        line = f"[{source}] {evidence}"
        if url:
            line += f" - {url}"
        story.append(Paragraph(line, styles["Subtle"]))

    def _draw_header_footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.setLineWidth(0.6)
        canvas.line(doc.leftMargin, A4[1] - 0.9 * cm, A4[0] - doc.rightMargin, A4[1] - 0.9 * cm)
        canvas.line(doc.leftMargin, 0.95 * cm, A4[0] - doc.rightMargin, 0.95 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawString(doc.leftMargin, A4[1] - 0.73 * cm, _clip_text(payload.get("variant_title") or "Architecture Workflow", 58))
        canvas.drawRightString(A4[0] - doc.rightMargin, 0.72 * cm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_header_footer, onLaterPages=_draw_header_footer)


def _build_markdown_report(payload: Dict[str, Any]) -> str:
    lines: List[str] = [
        f"# {payload.get('title')}",
        "",
        payload.get("subtitle") or "",
        "",
        "## Executive Summary",
        payload.get("executive_summary") or "",
        "",
        "## 2D Workflow System Design Architecture",
        f"- graph_mode: {(payload.get('graph_summary') or {}).get('graph_mode')}",
        f"- node_count: {(payload.get('graph_summary') or {}).get('node_count')}",
        f"- edge_count: {(payload.get('graph_summary') or {}).get('edge_count')}",
        "",
        "## Implementation Guidance",
    ]

    for step in payload.get("implementation_steps") or []:
        lines.append(f"- {step}")

    lines.extend(["", "## Dependencies (Current vs Latest)"])
    for dep in payload.get("dependencies") or []:
        lines.append(
            "- "
            f"{dep.get('name')} [{dep.get('ecosystem')}] "
            f"current={dep.get('current_version')} latest={dep.get('latest_version') or 'unknown'} "
            f"status={dep.get('update_status')}"
        )
        lines.append(f"  - why_used: {dep.get('why_used')}")
        if dep.get("doc_url"):
            lines.append(f"  - docs: {dep.get('doc_url')}")
        if dep.get("changelog_url"):
            lines.append(f"  - changelog: {dep.get('changelog_url')}")

    lines.extend(["", "## Risk Controls"])
    for item in payload.get("risk_controls") or []:
        lines.append(f"- {item}")

    lines.extend(["", "## References"])
    for ref in payload.get("references") or []:
        evidence = ref.get("evidence") or ""
        url = ref.get("url") or ""
        lines.append(f"- {ref.get('source')}: {evidence} {url}".strip())

    return "\n".join(lines).strip() + "\n"


def generate_variant_report_artifacts(
    report_id: str,
    reports_root: Path,
    repository_full_name: str,
    document_id: str,
    variant_row_id: str,
    variant_title: str,
    variant_payload: Dict[str, Any],
    architecture_context: Dict[str, Any],
    graph_payload: Dict[str, Any],
    include_official_references: bool = True,
) -> Dict[str, Any]:
    reports_root.mkdir(parents=True, exist_ok=True)

    static_summary = architecture_context.get("static") or {}
    runtime_summary = architecture_context.get("runtime") or {}
    major_changes = [str(item) for item in (variant_payload.get("major_changes") or [])]
    profile = str(variant_payload.get("target_profile") or "balanced").lower()

    dependencies: List[Dict[str, Any]] = []
    for dep in list(variant_payload.get("dependency_versions_used") or [])[:80]:
        name = str(dep.get("name") or "").strip()
        if not name:
            continue

        ecosystem = _detect_dependency_ecosystem(dep)
        current_version = _normalize_current_version(str(dep.get("version") or "unspecified"))
        latest_meta = _fetch_latest_npm(name) if ecosystem == "npm" else _fetch_latest_pypi(name)
        latest_version = latest_meta.get("latest_version")
        references = list(latest_meta.get("references") or [])

        if not include_official_references:
            references = [
                ref for ref in references
                if str(ref.get("source") or "") not in {"official_docs", "official_changelog"}
            ]
            latest_meta = {
                **latest_meta,
                "doc_url": None,
                "changelog_url": None,
            }

        update_status = "unknown"
        if current_version == "unspecified":
            update_status = "version_not_pinned"
        elif latest_version and _normalize_current_version(str(latest_version)) != current_version:
            update_status = "update_available"
        elif latest_version:
            update_status = "up_to_date"

        dependencies.append(
            {
                "name": name,
                "ecosystem": ecosystem,
                "source": dep.get("source"),
                "scope": dep.get("scope"),
                "current_version": current_version,
                "latest_version": latest_version,
                "update_status": update_status,
                "why_used": _derive_dependency_reason(name, major_changes, profile),
                "summary": latest_meta.get("summary"),
                "doc_url": latest_meta.get("doc_url"),
                "changelog_url": latest_meta.get("changelog_url"),
                "registry_url": latest_meta.get("registry_url"),
                "references": references,
            }
        )

    dependency_updates = sum(1 for dep in dependencies if dep.get("update_status") == "update_available")
    implementation_steps = _build_implementation_steps(variant_title, major_changes, dependencies)
    risk_controls = [
        "Keep immutable snapshot untouched and perform all work in isolated generated workspace.",
        "Apply dependency upgrades behind compatibility tests before production rollout.",
        "Use canary release and SLO-based rollback triggers for each high-risk change.",
        "Maintain trace/metrics parity to confirm architecture behavior after migration.",
    ]

    base_payload = {
        "repository": repository_full_name,
        "document_id": document_id,
        "variant_id": variant_row_id,
        "variant_title": variant_title,
        "target_profile": profile,
        "major_changes": major_changes,
        "runtime_services": runtime_summary.get("services") or [],
        "static_dependency_files": static_summary.get("dependency_files") or [],
        "dependency_updates": dependency_updates,
        "dependencies": [
            {
                "name": dep.get("name"),
                "ecosystem": dep.get("ecosystem"),
                "current_version": dep.get("current_version"),
                "latest_version": dep.get("latest_version"),
                "update_status": dep.get("update_status"),
                "why_used": dep.get("why_used"),
            }
            for dep in dependencies[:30]
        ],
        "graph_summary": {
            "graph_mode": graph_payload.get("graph_mode") or "ultra",
            "node_count": len(graph_payload.get("nodes") or []),
            "edge_count": len(graph_payload.get("edges") or []),
            "layers": graph_payload.get("layers") or [],
        },
    }

    ai_payload = _enhance_with_azure_openai(base_payload)
    reasoning_engine = "langgraph+azure-openai-report" if ai_payload else "deterministic-report-reasoning"

    references: List[Dict[str, Any]] = [
        {"source": "architecture_document", "evidence": f"document_id={document_id}"},
        {"source": "variant", "evidence": f"variant_id={variant_row_id}"},
        {
            "source": "graph",
            "evidence": f"nodes={len(graph_payload.get('nodes') or [])}, edges={len(graph_payload.get('edges') or [])}",
        },
    ]
    for dep in dependencies:
        references.extend(dep.get("references") or [])

    subtitle = (
        f"Repository: {repository_full_name} | Variant: {variant_title} | Generated at: {datetime.utcnow().isoformat()}"
    )
    executive_summary = (
        ai_payload.get("executive_summary")
        if isinstance(ai_payload.get("executive_summary"), str)
        else (
            f"This workflow report analyzes {variant_title} with {len(major_changes)} major changes, "
            f"{len(dependencies)} mapped dependencies, and {dependency_updates} potential version updates "
            "against latest stable package releases from PyPI/NPM."
        )
    )

    implementation_guidance = ai_payload.get("implementation_guidance") if isinstance(ai_payload.get("implementation_guidance"), list) else []
    if implementation_guidance:
        implementation_steps = [str(item) for item in implementation_guidance[:20]]

    ai_risk_controls = ai_payload.get("risk_controls") if isinstance(ai_payload.get("risk_controls"), list) else []
    if ai_risk_controls:
        risk_controls = [str(item) for item in ai_risk_controls[:12]]

    report_payload = {
        "title": f"Architecture Workflow Report - {variant_title}",
        "subtitle": subtitle,
        "repository": repository_full_name,
        "variant_title": variant_title,
        "target_profile": profile,
        "generated_at": datetime.utcnow().isoformat(),
        "executive_summary": executive_summary,
        "architecture_narrative": ai_payload.get("architecture_narrative") if isinstance(ai_payload.get("architecture_narrative"), str) else "",
        "graph_summary": {
            "graph_mode": graph_payload.get("graph_mode") or "ultra",
            "node_count": len(graph_payload.get("nodes") or []),
            "edge_count": len(graph_payload.get("edges") or []),
        },
        "graph_payload": graph_payload,
        "major_changes": major_changes,
        "dependencies": dependencies,
        "implementation_steps": implementation_steps,
        "risk_controls": risk_controls,
        "references": references,
    }

    markdown = _build_markdown_report(report_payload)

    markdown_path = reports_root / f"workflow_report_{report_id}.md"
    pdf_path = reports_root / f"workflow_report_{report_id}.pdf"

    markdown_path.write_text(markdown, encoding="utf-8")
    _write_pdf_report(pdf_path, report_payload)

    return {
        "markdown_path": str(markdown_path),
        "pdf_path": str(pdf_path),
        "summary": {
            "report_id": report_id,
            "reasoning_engine": reasoning_engine,
            "dependency_count": len(dependencies),
            "dependency_updates_available": dependency_updates,
            "graph_node_count": len(graph_payload.get("nodes") or []),
            "graph_edge_count": len(graph_payload.get("edges") or []),
            "generated_at": datetime.utcnow().isoformat(),
        },
    }
