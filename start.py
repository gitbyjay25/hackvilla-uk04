#!/usr/bin/env python
"""
Nexarch Multi-Server Launcher
Starts both FastAPI and MCP servers in separate background terminals.

Usage:
  python start.py              # Start both servers
  python start.py --fastapi    # Start only FastAPI server
  python start.py --mcp        # Start only MCP server
  python start.py --status     # Check server status
"""
import subprocess
import sys
import os
import time
import requests
from pathlib import Path

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}[OK] {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}[ERROR] {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.CYAN}[INFO] {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}[WARNING] {text}{Colors.END}")

def get_project_root():
    """Get the project root directory"""
    return Path(__file__).parent.absolute()

def start_fastapi_server():
    """Start FastAPI server in a new PowerShell terminal"""
    project_root = get_project_root()
    server_dir = project_root / "Server"
    
    print_info(f"Starting FastAPI server in new terminal...")
    print_info(f"  Host: 127.0.0.1:8000")
    print_info(f"  Directory: {server_dir}")
    
    # PowerShell command to start FastAPI
    powershell_cmd = f"""
    $env:PYTHONIOENCODING='utf-8'
    cd '{server_dir}'
    # Load .env file if exists
    if (Test-Path .env) {{
        Get-Content .env | ForEach-Object {{
            if ($_ -match '^([^=]+)=(.*)$') {{
                $name = $matches[1]
                $value = $matches[2]
                Set-Item -Path "env:$name" -Value $value
            }}
        }}
        Write-Host '[OK] Environment variables loaded from .env' -ForegroundColor Green
    }}
    Write-Host '[*] Starting FastAPI Server (Nexarch)...' -ForegroundColor Green
    Write-Host '    Host: 127.0.0.1:8000' -ForegroundColor Cyan
    Write-Host '    Press Ctrl+C to stop' -ForegroundColor Yellow
    Write-Host ''
    python main.py
    """
    
    # Start PowerShell in a new window
    cmd = [
        'powershell.exe',
        '-NoExit',
        '-Command',
        powershell_cmd
    ]
    
    try:
        subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=str(server_dir)
        )
        print_success("FastAPI terminal launched")
        return True
    except Exception as e:
        print_error(f"Failed to start FastAPI server: {e}")
        return False

def start_mcp_server():
    """Start MCP server in a new PowerShell terminal"""
    project_root = get_project_root()
    
    print_info(f"Starting MCP server in new terminal...")
    print_info(f"  Host: 127.0.0.1:8001 (localhost)")
    print_info(f"  Directory: {project_root}")
    
    # PowerShell command to start MCP server
    powershell_cmd = f"""
    $env:PYTHONIOENCODING='utf-8'
    cd '{project_root}'
    # Load .env file from Server directory
    if (Test-Path Server\\.env) {{
        Get-Content Server\\.env | ForEach-Object {{
            if ($_ -match '^([^=]+)=(.*)$') {{
                $name = $matches[1]
                $value = $matches[2]
                Set-Item -Path "env:$name" -Value $value
            }}
        }}
        Write-Host '[OK] Environment variables loaded from Server/.env' -ForegroundColor Green
    }}
    Write-Host '[*] Starting MCP Server (Nexarch)...' -ForegroundColor Green
    Write-Host '    Host: 127.0.0.1:8001 (localhost only)' -ForegroundColor Cyan
    Write-Host '    Transport: stdio (for Claude Desktop)' -ForegroundColor Cyan
    Write-Host '    Press Ctrl+C to stop' -ForegroundColor Yellow
    Write-Host ''
    python start_mcp.py
    """
    
    # Start PowerShell in a new window
    cmd = [
        'powershell.exe',
        '-NoExit',
        '-Command',
        powershell_cmd
    ]
    
    try:
        subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=str(project_root)
        )
        print_success("MCP terminal launched")
        return True
    except Exception as e:
        print_error(f"Failed to start MCP server: {e}")
        return False

def check_server_status():
    """Check if servers are running"""
    print_header("Server Status Check")
    
    # Check FastAPI
    print_info("Checking FastAPI server (127.0.0.1:8000)...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=3)
        if response.status_code == 200:
            print_success(f"FastAPI server is running (status: {response.status_code})")
            data = response.json()
            if 'status' in data:
                print(f"  Status: {data['status']}")
        else:
            print_warning(f"FastAPI server responded with status: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print_error("FastAPI server is not running (connection refused)")
    except requests.exceptions.Timeout:
        print_error("FastAPI server is not responding (timeout)")
    except Exception as e:
        print_error(f"Error checking FastAPI server: {e}")
    
    print()
    
    # Check MCP server
    print_info("Checking MCP server (127.0.0.1:8001)...")
    print_info("Note: MCP server typically runs in stdio mode for Claude Desktop")
    print_warning("Use --sse or --http flags to start MCP with HTTP transport for testing")

def main():
    """Main launcher function"""
    print_header("Nexarch Multi-Server Launcher")
    
    args = sys.argv[1:]
    
    # Check status mode
    if "--status" in args:
        check_server_status()
        return
    
    # Determine which servers to start
    start_both = not any(arg in args for arg in ["--fastapi", "--mcp"])
    start_fastapi = start_both or "--fastapi" in args
    start_mcp = start_both or "--mcp" in args
    
    success_count = 0
    
    if start_fastapi:
        print_info("Server 1: FastAPI (Network accessible)")
        if start_fastapi_server():
            success_count += 1
        time.sleep(2)  # Wait a bit before starting next server
    
    if start_mcp:
        print_info("Server 2: MCP (Local only)")
        if start_mcp_server():
            success_count += 1
        time.sleep(2)
    
    print()
    print_header("Launch Summary")
    
    if start_both and success_count == 2:
        print_success("Both servers launched successfully!")
    elif success_count > 0:
        print_success(f"{success_count} server(s) launched successfully!")
    else:
        print_error("Failed to launch servers")
        return 1
    
    print()
    print_info("Server Information:")
    print(f"  {Colors.CYAN}FastAPI:{Colors.END} http://127.0.0.1:8000 (localhost only)")
    print(f"  {Colors.CYAN}MCP:{Colors.END}     127.0.0.1:8001 (localhost only, stdio mode)")
    print()
    print_info("Useful URLs:")
    print(f"  {Colors.CYAN}API Docs:{Colors.END}  http://localhost:8000/docs")
    print(f"  {Colors.CYAN}Health:{Colors.END}    http://localhost:8000/api/v1/health")
    print()
    print_info("Commands:")
    print(f"  {Colors.CYAN}Check status:{Colors.END} python start.py --status")
    print(f"  {Colors.CYAN}Stop servers:{Colors.END} Close the terminal windows or press Ctrl+C")
    print()
    print_warning("Both servers are running in background terminals.")
    print_warning("Close the terminal windows to stop the servers.")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_warning("Launcher interrupted")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
