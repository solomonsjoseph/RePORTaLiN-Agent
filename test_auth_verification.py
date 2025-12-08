#!/usr/bin/env python3
"""Quick verification that auth enforcement works."""

import os
import sys

# Set env BEFORE imports
os.environ['MCP_AUTH_TOKEN'] = 'test-secret-token'
os.environ['MCP_AUTH_ENABLED'] = 'true'
os.environ['ENVIRONMENT'] = 'local'

# Clear caches BEFORE importing app modules
from server.config import get_settings
get_settings.cache_clear()
from server.auth import get_rotatable_secret
get_rotatable_secret.cache_clear()

# Now import and test
from fastapi.testclient import TestClient
from server.main import base_app

client = TestClient(base_app)

print("=" * 60)
print("AUTH ENFORCEMENT VERIFICATION")
print("=" * 60)

# Test 1: Health (public)
r = client.get('/health')
print(f"\n1. Health check (public): {r.status_code}")
assert r.status_code == 200, "Health should be 200"
print("   ✅ PASS - Health endpoint accessible")

# Test 2: Tools without auth (should fail)
r = client.get('/tools')
print(f"\n2. Tools (no auth): {r.status_code}")
assert r.status_code == 401, f"Expected 401, got {r.status_code}"
print("   ✅ PASS - Auth required, rejected unauthenticated request")

# Test 3: Tools with wrong auth (should fail)
r = client.get('/tools', headers={'Authorization': 'Bearer wrong-token'})
print(f"\n3. Tools (wrong auth): {r.status_code}")
assert r.status_code == 401, f"Expected 401, got {r.status_code}"
print("   ✅ PASS - Invalid token rejected")

# Test 4: Tools with correct auth (should succeed)
r = client.get('/tools', headers={'Authorization': 'Bearer test-secret-token'})
print(f"\n4. Tools (correct auth): {r.status_code}")
assert r.status_code == 200, f"Expected 200, got {r.status_code}"
assert "tools" in r.json(), "Response should contain 'tools'"
print("   ✅ PASS - Valid token accepted")

# Test 5: Info endpoint without auth (should fail)
r = client.get('/info')
print(f"\n5. Info (no auth): {r.status_code}")
assert r.status_code == 401, f"Expected 401, got {r.status_code}"
print("   ✅ PASS - Info endpoint requires auth")

# Test 6: MCP SSE without auth (should fail)
r = client.get('/mcp/sse')
print(f"\n6. MCP SSE (no auth): {r.status_code}")
assert r.status_code == 401, f"Expected 401, got {r.status_code}"
print("   ✅ PASS - MCP SSE endpoint requires auth")

print("\n" + "=" * 60)
print("ALL SECURITY TESTS PASSED ✅")
print("=" * 60)
