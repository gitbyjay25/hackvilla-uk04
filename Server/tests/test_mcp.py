"""
Test MCP Server Tools Locally
This bypasses the MCP protocol and calls tools directly for testing
"""
from mcp.tools import MCPTools
import json

def test_mcp_tools():
    """Test all MCP tools"""
    tools = MCPTools()
    
    print("=" * 80)
    print("Testing Nexarch MCP Tools")
    print("=" * 80)
    
    # Test 1: Get Architecture
    print("\n1. GET CURRENT ARCHITECTURE")
    print("-" * 80)
    try:
        result = tools.get_current_architecture()
        print(f"✓ Found {len(result.get('nodes', []))} nodes")
        print(f"✓ Found {len(result.get('edges', []))} edges")
        print(json.dumps(result, indent=2)[:500] + "...")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 2: Get Issues
    print("\n2. GET DETECTED ISSUES")
    print("-" * 80)
    try:
        result = tools.get_detected_issues()
        print(f"✓ Found {result.get('total_count', 0)} issues")
        for severity, issues in result.get('by_severity', {}).items():
            print(f"  - {severity}: {len(issues)} issues")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 3: Generate Workflows
    print("\n3. GENERATE WORKFLOWS")
    print("-" * 80)
    try:
        result = tools.generate_workflows()
        print(f"✓ Generated {result.get('count', 0)} workflows")
        for workflow in result.get('workflows', []):
            print(f"  - {workflow.get('name')}: "
                  f"complexity={workflow.get('complexity_score')}, "
                  f"risk={workflow.get('risk_score')}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 4: Compare Workflows
    print("\n4. COMPARE WORKFLOWS")
    print("-" * 80)
    try:
        result = tools.compare_workflows()
        recommendation = result.get('recommendation', {})
        print(f"✓ Recommended: {recommendation.get('workflow')}")
        print(f"  Reason: {recommendation.get('reason')}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 5: Graph Analysis
    print("\n5. GRAPH ANALYSIS")
    print("-" * 80)
    try:
        result = tools.get_graph_analysis()
        metrics = result.get('graph_metrics', {})
        print(f"✓ Nodes: {metrics.get('node_count')}")
        print(f"✓ Edges: {metrics.get('edge_count')}")
        print(f"✓ Is DAG: {metrics.get('is_dag')}")
        print(f"✓ Bottlenecks: {len(metrics.get('bottlenecks', []))}")
        print(f"✓ Cycles: {len(metrics.get('cycles', []))}")
        
        insights = result.get('insights', [])
        if insights:
            print("\nInsights:")
            for insight in insights:
                print(f"  {insight}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "=" * 80)
    print("Testing Complete")
    print("=" * 80)


if __name__ == "__main__":
    test_mcp_tools()
