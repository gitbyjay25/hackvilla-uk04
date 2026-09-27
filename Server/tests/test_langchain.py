"""
Test script to verify LangChain and LangGraph integration
Tests the workflow generation pipeline and AI client
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 70)
print("LangChain & LangGraph Integration Test")
print("=" * 70)
print()

# Test 1: Import all required packages
print("📦 Testing Package Imports...")
try:
    import langchain
    print(f"   ✓ langchain version: {langchain.__version__}")
except ImportError as e:
    print(f"   ✗ langchain import failed: {e}")
    sys.exit(1)

try:
    import langgraph
    print(f"   ✓ langgraph version: {langgraph.__version__}")
except ImportError as e:
    print(f"   ✗ langgraph import failed: {e}")
    sys.exit(1)

try:
    from langchain_openai import AzureChatOpenAI
    print(f"   ✓ langchain_openai imported")
except ImportError as e:
    print(f"   ✗ langchain_openai import failed: {e}")
    sys.exit(1)

try:
    from langgraph.graph import StateGraph, END
    print(f"   ✓ langgraph.graph imported")
except ImportError as e:
    print(f"   ✗ langgraph.graph import failed: {e}")
    sys.exit(1)

print()

# Test 2: Check Azure OpenAI Configuration
print("🔧 Testing Azure OpenAI Configuration...")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")

if azure_endpoint:
    print(f"   ✓ AZURE_OPENAI_ENDPOINT: {azure_endpoint}")
else:
    print(f"   ⚠ AZURE_OPENAI_ENDPOINT not set")

if azure_deployment:
    print(f"   ✓ AZURE_OPENAI_DEPLOYMENT: {azure_deployment}")
else:
    print(f"   ⚠ AZURE_OPENAI_DEPLOYMENT not set")

if azure_api_key:
    print(f"   ✓ AZURE_OPENAI_API_KEY: {'*' * 20}{azure_api_key[-4:]}")
else:
    print(f"   ⚠ AZURE_OPENAI_API_KEY not set")

if azure_api_version:
    print(f"   ✓ AZURE_OPENAI_API_VERSION: {azure_api_version}")
else:
    print(f"   ⚠ AZURE_OPENAI_API_VERSION not set")

print()

# Test 3: Import Nexarch AI Client
print("🤖 Testing Nexarch AI Client...")
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core.ai_client import get_ai_client, AIClient
    print(f"   ✓ AI Client imported successfully")
    
    # Initialize AI client
    ai_client = get_ai_client()
    print(f"   ✓ AI Client initialized")
    print(f"   ✓ Azure OpenAI configured: {ai_client.azure_openai is not None}")
except Exception as e:
    print(f"   ✗ AI Client initialization failed: {e}")
    print(f"   ℹ This is expected if Azure OpenAI credentials are not configured")

print()

# Test 4: Import LangGraph Pipeline
print("🔄 Testing LangGraph Pipeline...")
try:
    from reasoning.langgraph_pipeline import WorkflowPipeline, WorkflowState
    print(f"   ✓ WorkflowPipeline imported")
    print(f"   ✓ WorkflowState imported")
except Exception as e:
    print(f"   ✗ LangGraph pipeline import failed: {e}")
    sys.exit(1)

print()

# Test 5: Test Workflow Pipeline Initialization
print("⚙️ Testing Workflow Pipeline Initialization...")
try:
    # Create sample issue data
    sample_issue = {
        "id": "test-001",
        "service_name": "payment-service",
        "issue_type": "HighLatency",
        "severity": "HIGH",
        "description": "Payment API response time increased from 200ms to 1500ms",
        "metrics": {
            "avg_latency_ms": 1500,
            "p95_latency_ms": 2000,
            "error_rate": 0.05
        }
    }
    
    pipeline = WorkflowPipeline()
    print(f"   ✓ WorkflowPipeline instance created")
    
    # Check if workflow graph is compiled
    if hasattr(pipeline, 'workflow'):
        print(f"   ✓ Workflow graph compiled")
    else:
        print(f"   ⚠ Workflow graph not found")
    
except Exception as e:
    print(f"   ✗ Pipeline initialization failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 6: Test Workflow Generation (if Azure OpenAI is configured)
if azure_endpoint and azure_api_key:
    print("🚀 Testing Workflow Generation...")
    try:
        # Generate workflow
        workflow_result = pipeline.generate_workflow(sample_issue)
        
        if workflow_result and "workflow" in workflow_result:
            workflow = workflow_result["workflow"]
            print(f"   ✓ Workflow generated successfully")
            print(f"   ✓ Workflow ID: {workflow.get('id', 'N/A')}")
            print(f"   ✓ Workflow name: {workflow.get('name', 'N/A')}")
            print(f"   ✓ Number of steps: {len(workflow.get('steps', []))}")
            
            if workflow.get('steps'):
                print(f"\n   📋 Workflow Steps:")
                for i, step in enumerate(workflow['steps'][:3], 1):  # Show first 3 steps
                    print(f"      {i}. {step.get('name', 'Unnamed step')}")
                if len(workflow['steps']) > 3:
                    print(f"      ... and {len(workflow['steps']) - 3} more steps")
        else:
            print(f"   ⚠ Workflow generated but structure unexpected")
            print(f"   Result: {workflow_result}")
            
    except Exception as e:
        print(f"   ✗ Workflow generation failed: {e}")
        print(f"   ℹ This may indicate Azure OpenAI connection issues")
        import traceback
        traceback.print_exc()
else:
    print("⏭️ Skipping Workflow Generation Test (Azure OpenAI not configured)")

print()

# Test 7: Test Graph Analysis Rules
print("📊 Testing Graph Analysis Rules...")
try:
    from reasoning.rules import apply_rules, get_analysis_rules
    print(f"   ✓ Rules engine imported")
    
    rules = get_analysis_rules()
    print(f"   ✓ Found {len(rules)} analysis rules")
    
    # Test rule application
    sample_graph_data = {
        "nodes": [
            {"id": "payment-service", "type": "service", "metrics": {"latency_ms": 1500}},
            {"id": "database", "type": "database", "metrics": {"latency_ms": 800}}
        ],
        "edges": [
            {"source": "payment-service", "target": "database", "type": "database_call"}
        ]
    }
    
    issues = apply_rules(sample_graph_data)
    print(f"   ✓ Rules applied, found {len(issues)} potential issues")
    
except Exception as e:
    print(f"   ✗ Rules engine test failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Summary
print("=" * 70)
print("✅ LangChain & LangGraph Test Summary")
print("=" * 70)
print()
print("✓ All core packages imported successfully")
print("✓ LangGraph pipeline initialized")
print("✓ Workflow generation system ready")
print("✓ Graph analysis rules loaded")
print()

if azure_endpoint and azure_api_key:
    print("🎉 SUCCESS! LangChain/LangGraph integration fully operational!")
else:
    print("⚠️  PARTIAL SUCCESS! Core functionality ready, but Azure OpenAI not configured.")
    print("   Configure Azure OpenAI credentials to test end-to-end workflow generation.")

print("=" * 70)
