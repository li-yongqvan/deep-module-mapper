"""Deep Module Mapper Python parser.

Public API: ``scan_codebase``.  Everything else in the package is private.
"""

from ._scanner import scan_codebase

__all__ = ["scan_codebase"]
