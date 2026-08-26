"""Sample package for parser tests."""

from .core import User, save_user  # re-exports (Q4/F18)

SOME_CONSTANT = 42

__all__ = ["save_user", "User", "SOME_CONSTANT"]
