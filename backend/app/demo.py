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
    Demo("Platform", "jun@pharmacrm.test", "Jun Espino", "Developer Admin · apps, log, company, accounts", admin=True),
)
