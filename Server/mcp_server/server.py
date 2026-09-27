from fastmcp import FastMCP
from typing import Dict, Any, List, Optional
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.tools import MCPTools

# Create MCP server
mcp = FastMCP("Nexarch Architecture Intelligence")

# Initialize tools with multi-tenant support
tools = MCPTools(default_tenant_id="default")


@mcp.tool()
def get_current_architecture(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get current architecture graph with nodes, edges, and metrics
    
    Args:
        tenant_id: Optional tenant ID for multi-tenant isolation (defaults to "default")
    """
    return tools.get_current_architecture(tenant_id)


@mcp.tool()
async def get_detected_issues(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get all detected architectural issues with AI enhancement
    
    Args:
        tenant_id: Optional tenant ID for multi-tenant isolation (defaults to "default")
    """
    return await tools.get_detected_issues(tenant_id)


@mcp.tool()
async def generate_workflows(tenant_id: Optional[str] = None, goal: str = "optimize_performance") -> Dict[str, Any]:
    """Generate 3 workflow alternatives using LangGraph + Azure OpenAI reasoning
    
    Args:
        tenant_id: Optional tenant ID for multi-tenant isolation (defaults to "default")
        goal: Optimization goal - optimize_performance, reduce_cost, minimize_changes
    """
    return await tools.generate_workflows(tenant_id, goal)


@mcp.tool()
async def compare_workflows(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Compare generated workflows with intelligent multi-criteria recommendation
    
    Args:
        tenant_id: Optional tenant ID for multi-tenant isolation (defaults to "default")
    """
    return await tools.compare_workflows(tenant_id)


@mcp.tool()
async def explain_decision(workflow_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Explain reasoning behind a specific workflow decision with detailed analysis
    
    Args:
        workflow_id: ID of the workflow to explain
        tenant_id: Optional tenant ID for multi-tenant isolation (defaults to "default")
    """
    return await tools.explain_decision(workflow_id, tenant_id)


@mcp.tool()
def get_graph_analysis(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get advanced graph analysis (centrality, bottlenecks, cycles) with AI insights
    
    Args:
        tenant_id: Optional tenant ID for multi-tenant isolation (defaults to "default")
    """
    return tools.get_graph_analysis(tenant_id)


if __name__ == "__main__":
    print("Starting Nexarch MCP Server with multi-tenant support...")
    mcp.run()
