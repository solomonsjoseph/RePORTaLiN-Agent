"""Backward-compatible shim for server/__main__.py."""
import sys

from reportalin.server.__main__ import main  # noqa: F401

if __name__ == "__main__":
    sys.exit(main())
