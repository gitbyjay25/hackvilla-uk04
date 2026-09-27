#!/usr/bin/env python
"""
Nexarch MCP Server Launcher
Run this script to start the MCP server for Claude Desktop integration.

Usage:
  python start_mcp.py              # Start with stdio transport (for Claude Desktop)
  python start_mcp.py --sse        # Start with SSE transport (for web clients)
  python start_mcp.py --http       # Start with streamable HTTP transport
"""
import sys
import os

# Add Server directory to path FIRST (before any imports)
server_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Server')
sys.path.insert(0, server_dir)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = os.path.join(server_dir, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ Loaded environment from {env_path}", file=sys.stderr)
    else:
        print(f"⚠️  No .env file found at {env_path}", file=sys.stderr)
except ImportError:
    print("⚠️  python-dotenv not installed, environment variables not loaded", file=sys.stderr)
    print("   Install with: pip install python-dotenv", file=sys.stderr)

print("🚀 Starting Nexarch MCP Server...", file=sys.stderr)
print(f"   Server directory: {server_dir}", file=sys.stderr)

try:
    from mcp_server.server import mcp
    
    # Determine transport mode
    transport = "stdio"
    host = "127.0.0.1"  # MCP server runs locally
    port = 8001
    
    if "--sse" in sys.argv:
        transport = "sse"
    elif "--http" in sys.argv:
        transport = "streamable-http"
    
    print(f"✅ MCP Server initialized with 6 tools (transport: {transport})", file=sys.stderr)
    if transport == "stdio":
        mcp.run(transport=transport)
    else:
        print(f"   Running on {host}:{port}", file=sys.stderr)
        mcp.run(transport=transport, host=host, port=port)
except ImportError as e:
    print(f"❌ Error: {e}", file=sys.stderr)
    print("\nTroubleshooting:", file=sys.stderr)
    print("1. Make sure fastmcp is installed: pip install fastmcp", file=sys.stderr)
    print("2. Check if pydantic version is compatible", file=sys.stderr)
    print("3. Try: pip install --upgrade pydantic fastmcp", file=sys.stderr)
    sys.exit(1)
