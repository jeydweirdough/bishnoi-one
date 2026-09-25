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
    Demo("Executive Admin", "deo@pharmacrm.test", "Deo Castillo", "Department Staff · Executive Admin"),
    Demo("Executive Admin", "mila@pharmacrm.test", "Mila Aguilar", "Management · sees every division"),
    Demo("Executive Admin", "ramon@pharmacrm.test", "Ramon Santos", "Executive · everything, read-only"),
    Demo("Executive Admin", "teresa@pharmacrm.test", "Teresa Abad", "Department Staff · Human Resource"),
    Demo("Admin", "carmen@pharmacrm.test", "Carmen Villanueva", "Admin · every setting, owns the company", admin=True),
)
