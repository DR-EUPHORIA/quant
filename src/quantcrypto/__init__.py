"""Legacy compatibility shim for the old crypto package name.

This package is intentionally kept as a thin import alias only.
All active development should happen under ``markets.crypto``.
"""

from markets.crypto import *  # noqa: F401,F403
