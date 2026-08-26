"""Utility helpers."""

from sample_pkg import core as core_mod  # F17: submodule over __init__ port


def format_name(name: str) -> str:
    """Format a name for display."""
    return name.strip().title()


def _secret_helper():
    return "secret"


class Formatter:
    """Formats things."""

    def format(self, value):
        """Format a single value."""
        return str(value)


def use_builtins(items):
    """Call builtins; these must not become unresolved symbols (F3)."""
    return list(map(len, items))


def use_submodule():
    """Call into the core submodule imported via `from sample_pkg import core`."""
    return core_mod.save_user("x", "y")
