"""
Backward-compatible shim for shared/constants.py.

This module re-exports everything from the new location to maintain
backward compatibility during the refactoring process.

DEPRECATED: Import from reportalin.core.constants instead.
"""

# Re-export everything from new location for backward compatibility
from reportalin.core.constants import *  # noqa: F401, F403
