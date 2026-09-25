"""This app's demo accounts, for development.

`uv run python -m app.tools.users demo` makes them (password demo1234), and
the sign-in page lists the ones that exist here, so it only ever shows
accounts that can sign in to this app. Neither works in production.
"""

from dataclasses import dataclass

DEMO_PASSWORD = "demo1234"


@dataclass(frozen=True)
class Demo:
    group: str
    email: str
    name: str
    role: str
    admin: bool = False


DEMO_ACCOUNTS: tuple[Demo, ...] = (
    Demo("Finance", "joy@pharmacrm.test", "Joy Navarro", "Department Staff · Finance"),
    Demo("Finance", "fely@pharmacrm.test", "Fely Domingo", "Finance Staff · verifies order payments"),
)
