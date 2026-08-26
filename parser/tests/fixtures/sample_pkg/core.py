"""Core domain logic for the sample package."""


class User:
    """A user account."""

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        """Greet the user."""
        return f"Hello {self.name}"


def save_user(name: str, email: str, *, active: bool = True) -> User:
    """Persist a user to the database.

    Returns the created user record.
    """
    return User(name)


def _private_helper():
    """Should not appear as a port."""
    return None


def no_return_annotation(x):
    """Function without a return annotation (F2 regression)."""
    return x + 1
