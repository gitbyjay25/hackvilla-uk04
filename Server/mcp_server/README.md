# Nexarch MCP Server

FastMCP server for Architecture Intelligence.

## Installation

```bash
pip install -r ../requirements.txt
```

## Running the Server

```bash
python server.py
```

Or via stdio:

```bash
python -m mcp.server
```

## Available Tools

### get_current_architecture()

Returns the current architecture graph with nodes, edges, and metrics.

**Returns:**

```json
{
  "nodes": [...],
  "edges": [...],
  "metrics_summary": {...}
}
```

### get_detected_issues()

Returns all detected architectural issues with categorization.

**Returns:**

```json
{
  "issues": [...],
  "total_count": 5,
  "by_severity": {
    "critical": [...],
    "high": [...],
    "medium": [...]
  }
}
```

### generate_workflows()

Generates 3 workflow alternatives using LangGraph reasoning.

**Returns:**

```json
{
  "workflows": [...],
  "count": 3
}
```

### compare_workflows()

Compares generated workflows with recommendation.

**Returns:**

```json
{
  "workflows": [...],
  "comparison_matrix": {...},
  "recommendation": {
    "workflow": "Minimal Change",
    "reason": "..."
  }
}
```

### explain_decision(workflow_id: str)

Explains reasoning behind a specific workflow.

**Parameters:**

- `workflow_id`: Workflow ID to explain

**Returns:**

```json
{
  "workflow_id": "...",
  "workflow_name": "...",
  "reasoning": {...},
  "decision_factors": {...}
}
```

### get_graph_analysis()

Returns advanced graph analysis.

**Returns:**

```json
{
  "graph_metrics": {
    "node_count": 10,
    "edge_count": 15,
    "bottlenecks": [...],
    "cycles": [...],
    "critical_paths": [...]
  },
  "insights": [...]
}
```

## Integration

Use with Claude Desktop or any MCP-compatible client:

```json
{
  "mcpServers": {
    "nexarch": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "/path/to/Nexarch/Server"
    }
  }
}
```

## Design

- **Zero business logic**: MCP layer is a thin wrapper
- **Pure delegation**: All logic in services/reasoning layers
- **Stateless**: No side effects
- **JSON serializable**: All outputs are pure JSON
