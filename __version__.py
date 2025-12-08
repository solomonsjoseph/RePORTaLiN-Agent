"""
Version Information for RePORTaLiN-Specialist.

Single source of truth for version number used across the project.

This module is imported by multiple components (setup.py, docs/conf.py, main.py,
and all package __init__.py files) to ensure consistent version reporting throughout
the application.

Note:
    When bumping versions, update **only** the ``__version__`` string. The version
    tuple (``__version_info__``) is automatically derived, and the format is validated
    to ensure semantic versioning compliance.

Version Format Validation:
    The module automatically validates that ``__version__`` follows semantic versioning
    format (MAJOR.MINOR.PATCH) using regex pattern ``^\\d+\\.\\d+\\.\\d+$``.

    Valid formats:
        - ``"0.0.1"`` ✅
        - ``"1.0.0"`` ✅
        - ``"10.23.456"`` ✅

    Invalid formats (raise ValueError at import time):
        - ``"0.0.1a"`` ❌ (alpha suffix not allowed)
        - ``"v0.0.1"`` ❌ (prefix not allowed)
        - ``"0.1"`` ❌ (must have three components)
        - ``"0.0.1-rc1"`` ❌ (release candidate suffix not allowed)

Attributes:
    __version__: Current semantic version following MAJOR.MINOR.PATCH format.
        - MAJOR: Incompatible API changes
        - MINOR: New features (backward compatible)
        - PATCH: Bug fixes (backward compatible)

    __version_info__: Version information as a tuple of integers (MAJOR, MINOR, PATCH).
        Auto-derived from ``__version__`` string to ensure consistency.

Examples:
    Import and use the version string::

        from __version__ import __version__

        print(f"RePORTaLiN-Specialist version {__version__}")
        # Output: RePORTaLiN-Specialist version 0.0.2

    Access from command line::

        $ python main.py --version
        RePORTaLiN-Specialist 0.0.2

    Version tuple is auto-derived from version string::

        from __version__ import __version__, __version_info__

        print(f"Version: {__version__}")
        # Output: Version: 0.0.2

        print(f"Version tuple: {__version_info__}")
        # Output: Version tuple: (0, 0, 2)

        # The tuple is automatically derived, so they're always in sync
        assert __version_info__ == tuple(map(int, __version__.split('.')))

See Also:
    - :doc:`../docs/sphinx/changelog` - Complete version history
    - :mod:`main` - Main pipeline entry point
    - :mod:`config` - Configuration module
"""

import re

__version__: str = "2.1.0"

# Validate semantic versioning format (MAJOR.MINOR.PATCH)
if not re.match(r"^\d+\.\d+\.\d+$", __version__):
    raise ValueError(
        f"Invalid version format: {__version__}. "
        f"Must follow semantic versioning: MAJOR.MINOR.PATCH"
    )

# Auto-derive version tuple from version string to ensure consistency
_parts = tuple(map(int, __version__.split(".")))
__version_info__: tuple[int, int, int] = (_parts[0], _parts[1], _parts[2])

__all__ = ["__version__", "__version_info__"]
