"""Entry point exercising all edge kinds."""

import json  # stdlib -> ignored (D17)
import requests  # third-party -> externalModules
from . import utils  # relative from-import (module=None)
from .core import User, save_user  # from-import with ports
from .utils import format_name as fmt  # from-import with alias


class Admin(User):  # inheritance edge to core.User
    """An admin user."""

    def __init__(self, name: str):
        super().__init__(name)


@utils.Formatter  # decorator edge to utils.Formatter
class Decorated:
    """A class decorated with a foreign attribute."""


def main():
    user = save_user("alice", "a@example.com")  # call edge to core.save_user
    print(user)  # builtin -> skip
    name = fmt("bob")  # call edge to utils.format_name (via alias)
    _ = json.dumps({"name": name})  # stdlib -> skip
    req = requests.get("https://example.com")  # Attribute call to third-party
    admin = Admin("carol")
    return admin.greet()  # local-var method call -> skip


def annotate(u: User) -> User:  # annotation edges to core.User
    """Annotate with an imported type."""
    return u


def dynamic_load():
    module_name = "os"
    return __import__(module_name)  # dynamic import, non-literal target (Q5)


def undefined_call():
    return undefined_symbol()  # unresolved symbol (F3)


def attribute_undefined():
    return mystery_thing.call_me()  # unresolved base (F4 branch 3)
