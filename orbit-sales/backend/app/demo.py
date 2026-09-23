"""Sales' demo accounts, for development.

`uv run python -m app.tools.users demo` makes them (password demo1234), with
their role and team, and makes the teams they're in. The sign-in page lists
the ones that exist here, so it only ever shows accounts that can sign in to
Sales. Neither works in production.
"""

from dataclasses import dataclass

DEMO_PASSWORD = "demo1234"


@dataclass(frozen=True)
class Demo:
    group: str
    email: str
    name: str
    role: str  # what the sign-in page says they are
    access: str  # the role they're given (app/permissions.py)
    team: str | None = None


DEMO_ACCOUNTS: tuple[Demo, ...] = (
    Demo("Administration", "carmen@pharmacrm.test", "Carmen Villanueva", "Admin · users, roles, teams and the audit log", "Administrator"),
    Demo("Sales · B2C", "ben@pharmacrm.test", "Ben Cruz", "Rep · B2C MD Telesales", "Sales Rep", "B2C"),
    Demo("Sales · B2C", "tess@pharmacrm.test", "Tess Aquino", "Team Lead · B2C General", "Team Lead", "B2C"),
    Demo("Sales · STC, URO", "nena@pharmacrm.test", "Nena Gutierrez", "Rep · STC MD Telesales", "Sales Rep", "STC, URO"),
    Demo("Sales · STC, URO", "rico@pharmacrm.test", "Rico Padilla", "Rep · URO MD Telesales", "Sales Rep", "STC, URO"),
    Demo("Sales · B&B", "ana@pharmacrm.test", "Ana Reyes", "Rep · B&B MD Telesales + B2C General", "Sales Rep", "B&B"),
    Demo("Sales · B&B", "paolo@pharmacrm.test", "Paolo Mendoza", "Team Lead · B&B MD Telesales", "Team Lead", "B&B"),
    Demo("Sales · B&B", "lorna@pharmacrm.test", "Lorna Bautista", "Division Head · B&B", "Manager", "B&B"),
    Demo("Sales · B2B", "marlon@pharmacrm.test", "Marlon Yap", "Rep · B2B NBD", "Sales Rep", "B2B"),
    Demo("Sales · B2B", "dina@pharmacrm.test", "Dina Salazar", "Rep · B2B CRR", "Sales Rep", "B2B"),
    Demo("Sales · B2B", "noel@pharmacrm.test", "Noel Ramos", "Division Head · B2B", "Manager", "B2B"),
    Demo("Sales · HOS", "grace@pharmacrm.test", "Grace Lim", "Rep · HOS Hospital", "Sales Rep", "HOS"),
    Demo("Sales · HOS", "elmer@pharmacrm.test", "Elmer Tan", "Rep · HOS Telesales", "Sales Rep", "HOS"),
    Demo("Sales · HOS", "vicky@pharmacrm.test", "Vicky Ong", "Team Lead · HOS Hospital", "Team Lead", "HOS"),
    Demo("Sales · BID", "rosa@pharmacrm.test", "Rosa Ferrer", "Rep · BID Bidding", "Sales Rep", "BID"),
)
