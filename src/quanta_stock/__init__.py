"""Legacy compatibility shim for the old A-share package name.

This package is intentionally kept as a thin import alias only.
All active development should happen under ``markets.a_share``.
"""

from markets.a_share import *  # noqa: F401,F403
