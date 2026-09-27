from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, TypedDict, Annotated
import operator

from langgraph.graph import END, StateGraph


class AlphaPipelineState(TypedDict):
    """State for alpha code generation planning pipeline."""

    alpha_root: str
    snapshot_path: str
    variant: Dict[str, Any]
    deep_plan_markdown: str
    started_at: str

    file_inventory: Dict[str, Any]
    dependency_summary: Dict[str, Any]
    risk_summary: Dict[str, Any]
    transformation_steps: Annotated[List[Dict[str, Any]], operator.add]
    quality_gates: Dict[str, Any]
    summary: Dict[str, Any]


class AlphaCodegenPipeline:
    """Parallel planning pipeline used before alpha execution packaging.

    Fan-out branches after inventory:
    - dependency scan
    - risk scan
    - transformation step synthesis

    Fan-in merges all into a single quality plan summary.
    """

    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AlphaPipelineState)
        workflow.add_node("inventory", self._inventory)
        workflow.add_node("scan_dependencies", self._scan_dependencies)
        workflow.add_node("scan_risks", self._scan_risks)
        workflow.add_node("synthesize_steps", self._synthesize_steps)
        workflow.add_node("quality_gates", self._quality_gates)
        workflow.add_node("finalize", self._finalize)

        workflow.set_entry_point("inventory")

        workflow.add_edge("inventory", "scan_dependencies")
        workflow.add_edge("inventory", "scan_risks")
        workflow.add_edge("inventory", "synthesize_steps")

        workflow.add_edge("scan_dependencies", "quality_gates")
        workflow.add_edge("scan_risks", "quality_gates")
        workflow.add_edge("synthesize_steps", "quality_gates")

        workflow.add_edge("quality_gates", "finalize")
        workflow.add_edge("finalize", END)
        return workflow.compile()

    def _inventory(self, state: AlphaPipelineState) -> Dict[str, Any]:
        root = Path(state["alpha_root"])
        file_count = 0
        total_size = 0
        by_ext: Dict[str, int] = {}

        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".next", "dist", "build", "__pycache__"}]
            for name in files:
                path = Path(current) / name
                file_count += 1
                try:
                    total_size += path.stat().st_size
                except OSError:
                    pass
                ext = path.suffix.lower() or "<no_ext>"
                by_ext[ext] = by_ext.get(ext, 0) + 1

        return {
            "file_inventory": {
                "file_count": file_count,
                "total_size_bytes": total_size,
                "top_extensions": sorted(by_ext.items(), key=lambda x: x[1], reverse=True)[:20],
            }
        }

    def _scan_dependencies(self, state: AlphaPipelineState) -> Dict[str, Any]:
        root = Path(state["alpha_root"])
        dependency_files = []
        for marker in ["requirements.txt", "pyproject.toml", "package.json", "pom.xml", "build.gradle"]:
            dependency_files.extend([str(p.relative_to(root)) for p in root.rglob(marker)])

        return {
            "dependency_summary": {
                "dependency_files": sorted(set(dependency_files)),
                "has_python": any(p.endswith(("requirements.txt", "pyproject.toml")) for p in dependency_files),
                "has_node": any(p.endswith("package.json") for p in dependency_files),
            }
        }

    def _scan_risks(self, state: AlphaPipelineState) -> Dict[str, Any]:
        variant = state.get("variant", {})
        major_changes = variant.get("major_changes", []) if isinstance(variant, dict) else []

        risk_items = [
            "Transformation must occur only in alpha workspace",
            "Original snapshot must remain immutable",
            "Generated code must retain build/test integrity",
        ]
        if len(major_changes) >= 3:
            risk_items.append("Variant has broad change scope; enforce stricter validation gates")

        return {
            "risk_summary": {
                "risk_count": len(risk_items),
                "items": risk_items,
            }
        }

    def _synthesize_steps(self, state: AlphaPipelineState) -> Dict[str, Any]:
        variant = state.get("variant", {})
        major_changes = variant.get("major_changes", []) if isinstance(variant, dict) else []

        steps: List[Dict[str, Any]] = [
            {
                "step": 1,
                "name": "Copy snapshot into isolated alpha workspace",
                "type": "isolation",
            },
            {
                "step": 2,
                "name": "Apply variant-aware structural updates",
                "type": "architecture",
            },
            {
                "step": 3,
                "name": "Run test/build checks and package artifacts",
                "type": "validation",
            },
        ]

        for idx, change in enumerate(major_changes, start=4):
            steps.append(
                {
                    "step": idx,
                    "name": f"Implement major change: {change}",
                    "type": "major_change",
                }
            )

        return {"transformation_steps": steps}

    def _quality_gates(self, state: AlphaPipelineState) -> Dict[str, Any]:
        file_inventory = state.get("file_inventory", {})
        dependency_summary = state.get("dependency_summary", {})
        gates = {
            "workspace_isolation_required": True,
            "immutable_snapshot_required": True,
            "minimum_inventory_files": file_inventory.get("file_count", 0) > 0,
            "dependency_awareness": bool(dependency_summary.get("dependency_files", [])),
        }
        return {"quality_gates": gates}

    def _finalize(self, state: AlphaPipelineState) -> Dict[str, Any]:
        if not state.get("quality_gates"):
            return {}

        return {
            "summary": {
                "generated_at": datetime.utcnow().isoformat(),
                "pipeline": "alpha_codegen_parallel",
                "file_inventory": state.get("file_inventory", {}),
                "dependency_summary": state.get("dependency_summary", {}),
                "risk_summary": state.get("risk_summary", {}),
                "transformation_steps": state.get("transformation_steps", []),
                "quality_gates": state.get("quality_gates", {}),
            }
        }

    def run(self, alpha_root: Path, snapshot_path: Path, variant: Dict[str, Any], deep_plan_markdown: str) -> Dict[str, Any]:
        initial: AlphaPipelineState = {
            "alpha_root": str(alpha_root),
            "snapshot_path": str(snapshot_path),
            "variant": variant,
            "deep_plan_markdown": deep_plan_markdown,
            "started_at": datetime.utcnow().isoformat(),
            "file_inventory": {},
            "dependency_summary": {},
            "risk_summary": {},
            "transformation_steps": [],
            "quality_gates": {},
            "summary": {},
        }
        out = self.graph.invoke(initial)
        return out.get("summary", {})
