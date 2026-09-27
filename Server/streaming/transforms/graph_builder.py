"""
Graph Builder Transform
========================
Converts the live Pathway span table into incrementally-maintained
node and edge tables.

Nodes  — unique (tenant_id, service_name) pairs + aggregate metrics
Edges  — unique (tenant_id, service_name, downstream) pairs + aggregate
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathway as pw  # type: ignore[import]


def build_node_table(spans: "pw.Table") -> "pw.Table":
    """
    Group spans by (tenant_id, service_name) and compute:
    - total request count
    - running average latency
    - running error rate
    - node type classification
    """
    import pathway as pw  # type: ignore[import]

    nodes = spans.groupby(
        pw.this.tenant_id,
        pw.this.service_name,
    ).reduce(
        tenant_id=pw.this.tenant_id,
        service_name=pw.this.service_name,
        call_count=pw.reducers.count(),
        avg_latency_ms=pw.reducers.mean(pw.this.latency_ms),
        error_count=pw.reducers.sum(pw.this.is_error),
    )

    # Compute error_rate as a derived column
    nodes = nodes.with_columns(
        error_rate=pw.this.error_count / pw.apply(lambda c: max(c, 1), pw.this.call_count),
    )

    return nodes


def build_edge_table(spans: "pw.Table") -> "pw.Table":
    """
    Group spans that have a downstream service set to produce the
    dependency edge table.
    """
    import pathway as pw  # type: ignore[import]

    # Filter only spans that have a downstream dependency
    spans_with_downstream = spans.filter(pw.this.has_downstream)

    edges = spans_with_downstream.groupby(
        pw.this.tenant_id,
        pw.this.service_name,
        pw.this.downstream,
    ).reduce(
        tenant_id=pw.this.tenant_id,
        source=pw.this.service_name,
        target=pw.this.downstream,
        call_count=pw.reducers.count(),
        avg_latency_ms=pw.reducers.mean(pw.this.latency_ms),
        error_count=pw.reducers.sum(pw.this.is_error),
    )

    edges = edges.with_columns(
        error_rate=pw.this.error_count / pw.apply(lambda c: max(c, 1), pw.this.call_count),
    )

    return edges
