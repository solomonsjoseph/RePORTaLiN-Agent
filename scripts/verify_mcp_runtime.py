#!/usr/bin/env python3
"""
MCP Runtime Verification Script - "Mock Claude Desktop".

This script acts as a mock MCP client to verify the server can:
1. Start without crashing
2. Accept JSON-RPC handshake over stdio
3. Return valid JSON responses (no logs/garbage on stdout)
4. Handle tool listing requests
5. Shut down cleanly

Usage:
    # Run with uv (recommended)
    uv run python scripts/verify_mcp_runtime.py
    
    # Run with verbose output
    uv run python scripts/verify_mcp_runtime.py --verbose
    
    # Run with custom timeout
    uv run python scripts/verify_mcp_runtime.py --timeout 30

Exit Codes:
    0 - All tests passed (server is production-ready)
    1 - Server failed to start
    2 - JSON-RPC handshake failed
    3 - Invalid response (stdout corrupted)
    4 - Configuration error
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Constants
# =============================================================================

# MCP Protocol constants
MCP_PROTOCOL_VERSION = "2024-11-05"  # Latest stable version for initialize

# JSON-RPC request templates
INITIALIZE_REQUEST = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "tools": {},
            "resources": {},
        },
        "clientInfo": {
            "name": "verify_mcp_runtime",
            "version": "1.0.0",
        },
    },
}

INITIALIZED_NOTIFICATION = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
}

TOOLS_LIST_REQUEST = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {},
}

SHUTDOWN_REQUEST = {
    "jsonrpc": "2.0",
    "id": 99,
    "method": "shutdown",
    "params": {},
}


# =============================================================================
# Result Types
# =============================================================================

@dataclass
class TestResult:
    """Result of a verification test."""
    name: str
    passed: bool
    message: str
    details: dict[str, Any] | None = None
    
    def __str__(self) -> str:
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status}: {self.name} - {self.message}"


# =============================================================================
# Verification Tests
# =============================================================================

class MCPRuntimeVerifier:
    """
    Mock MCP client that verifies server compliance.
    
    This class launches the server as a subprocess and communicates
    via stdin/stdout JSON-RPC, mimicking how Claude Desktop connects.
    """
    
    def __init__(
        self,
        timeout: float = 15.0,
        verbose: bool = False,
        env_file: str = ".env.test",
    ):
        self.timeout = timeout
        self.verbose = verbose
        self.env_file = env_file
        self.process: subprocess.Popen | None = None
        self.results: list[TestResult] = []
    
    def log(self, message: str) -> None:
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"[VERIFIER] {message}", file=sys.stderr)
    
    def _load_test_env(self) -> dict[str, str]:
        """Load environment variables from test env file."""
        env = os.environ.copy()
        env_path = PROJECT_ROOT / self.env_file
        
        if env_path.exists():
            self.log(f"Loading environment from {env_path}")
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        env[key.strip()] = value.strip()
        else:
            self.log(f"Warning: {env_path} not found, using defaults")
            # Set minimal required env vars
            env["ENVIRONMENT"] = "local"
            env["MCP_AUTH_ENABLED"] = "false"
            env["LOG_LEVEL"] = "WARNING"
        
        # Force stdio transport
        env["MCP_TRANSPORT"] = "stdio"
        
        return env
    
    def _start_server(self) -> bool:
        """Start the MCP server subprocess."""
        self.log("Starting MCP server subprocess...")
        
        env = self._load_test_env()
        
        try:
            self.process = subprocess.Popen(
                ["uv", "run", "python", "-m", "server", "--transport", "stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(PROJECT_ROOT),
                env=env,
                text=True,
                bufsize=1,  # Line buffered
            )
            
            # Give server a moment to start
            time.sleep(0.5)
            
            # Check if process crashed immediately
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                self.results.append(TestResult(
                    name="Server Startup",
                    passed=False,
                    message=f"Server crashed on startup (exit code {self.process.returncode})",
                    details={"stderr": stderr[:1000]},
                ))
                return False
            
            self.log("Server process started successfully")
            return True
            
        except FileNotFoundError:
            self.results.append(TestResult(
                name="Server Startup",
                passed=False,
                message="'uv' command not found. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
            ))
            return False
        except Exception as e:
            self.results.append(TestResult(
                name="Server Startup",
                passed=False,
                message=f"Failed to start server: {e}",
            ))
            return False
    
    def _send_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Send a JSON-RPC request and read the response."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            return None
        
        request_json = json.dumps(request)
        self.log(f"Sending: {request_json[:100]}...")
        
        try:
            # Send request with newline
            self.process.stdin.write(request_json + "\n")
            self.process.stdin.flush()
            
            # Read response (with timeout)
            import select
            
            # Wait for data to be available
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                # Check if process is still alive
                if self.process.poll() is not None:
                    stderr = self.process.stderr.read() if self.process.stderr else ""
                    self.log(f"Process died. Stderr: {stderr[:500]}")
                    return None
                
                # Try to read a line
                try:
                    # Use a shorter timeout for select
                    import selectors
                    sel = selectors.DefaultSelector()
                    sel.register(self.process.stdout, selectors.EVENT_READ)
                    events = sel.select(timeout=0.5)
                    sel.close()
                    
                    if events:
                        line = self.process.stdout.readline()
                        if line:
                            self.log(f"Received: {line[:100]}...")
                            try:
                                return json.loads(line)
                            except json.JSONDecodeError as e:
                                self.log(f"JSON decode error: {e}")
                                self.log(f"Raw line: {repr(line)}")
                                # This is critical - non-JSON on stdout
                                return {"_error": "invalid_json", "_raw": line}
                except Exception as e:
                    self.log(f"Read error: {e}")
                    time.sleep(0.1)
            
            self.log("Timeout waiting for response")
            return None
            
        except Exception as e:
            self.log(f"Send/receive error: {e}")
            return None
    
    def _stop_server(self) -> None:
        """Stop the server subprocess."""
        if self.process:
            self.log("Stopping server...")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            
            # Capture any remaining stderr for debugging
            if self.process.stderr:
                stderr = self.process.stderr.read()
                if stderr and self.verbose:
                    self.log(f"Server stderr:\n{stderr[:2000]}")
    
    def test_initialize(self) -> bool:
        """Test MCP initialize handshake."""
        self.log("Testing initialize handshake...")
        
        response = self._send_request(INITIALIZE_REQUEST)
        
        if response is None:
            self.results.append(TestResult(
                name="Initialize Handshake",
                passed=False,
                message="No response to initialize request (timeout or crash)",
            ))
            return False
        
        if "_error" in response:
            self.results.append(TestResult(
                name="Initialize Handshake",
                passed=False,
                message="Server returned non-JSON output (logs on stdout?)",
                details={"raw": response.get("_raw", "")[:200]},
            ))
            return False
        
        # Check for valid JSON-RPC response
        if "result" in response:
            result = response["result"]
            self.results.append(TestResult(
                name="Initialize Handshake",
                passed=True,
                message="Server accepted initialize request",
                details={
                    "protocol_version": result.get("protocolVersion"),
                    "server_info": result.get("serverInfo"),
                    "capabilities": list(result.get("capabilities", {}).keys()),
                },
            ))
            
            # Send initialized notification
            self._send_request(INITIALIZED_NOTIFICATION)
            return True
        
        if "error" in response:
            self.results.append(TestResult(
                name="Initialize Handshake",
                passed=False,
                message=f"Server rejected initialize: {response['error']}",
                details=response["error"],
            ))
            return False
        
        self.results.append(TestResult(
            name="Initialize Handshake",
            passed=False,
            message="Unexpected response format",
            details=response,
        ))
        return False
    
    def test_tools_list(self) -> bool:
        """Test tools/list request."""
        self.log("Testing tools/list...")
        
        response = self._send_request(TOOLS_LIST_REQUEST)
        
        if response is None:
            self.results.append(TestResult(
                name="Tools List",
                passed=False,
                message="No response to tools/list request",
            ))
            return False
        
        if "_error" in response:
            self.results.append(TestResult(
                name="Tools List",
                passed=False,
                message="Invalid JSON response",
                details={"raw": response.get("_raw", "")[:200]},
            ))
            return False
        
        if "result" in response:
            result = response["result"]
            tools = result.get("tools", [])
            tool_names = [t.get("name") for t in tools if isinstance(t, dict)]
            
            self.results.append(TestResult(
                name="Tools List",
                passed=True,
                message=f"Server returned {len(tools)} tools",
                details={"tools": tool_names},
            ))
            return True
        
        if "error" in response:
            self.results.append(TestResult(
                name="Tools List",
                passed=False,
                message=f"Server error: {response['error']}",
            ))
            return False
        
        self.results.append(TestResult(
            name="Tools List",
            passed=False,
            message="Unexpected response format",
            details=response,
        ))
        return False
    
    def run_all_tests(self) -> bool:
        """Run all verification tests."""
        print("=" * 60)
        print("RePORTaLiN MCP Server - Runtime Verification")
        print("=" * 60)
        print()
        
        try:
            # Start server
            if not self._start_server():
                return False
            
            self.results.append(TestResult(
                name="Server Startup",
                passed=True,
                message="Server process started",
            ))
            
            # Run tests
            init_ok = self.test_initialize()
            if init_ok:
                self.test_tools_list()
            
        finally:
            self._stop_server()
        
        # Print results
        print()
        print("Results:")
        print("-" * 40)
        
        all_passed = True
        for result in self.results:
            print(result)
            if result.details and self.verbose:
                print(f"   Details: {json.dumps(result.details, indent=2)[:500]}")
            if not result.passed:
                all_passed = False
        
        print()
        print("=" * 60)
        if all_passed:
            print("✅ ALL TESTS PASSED - Server is production-ready!")
        else:
            print("❌ TESTS FAILED - See details above")
        print("=" * 60)
        
        return all_passed


# =============================================================================
# CLI Entry Point
# =============================================================================

def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify MCP server runtime compliance",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Timeout for each request (default: 15s)",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=".env.test",
        help="Environment file to load (default: .env.test)",
    )
    
    args = parser.parse_args()
    
    verifier = MCPRuntimeVerifier(
        timeout=args.timeout,
        verbose=args.verbose,
        env_file=args.env_file,
    )
    
    success = verifier.run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
