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
    Demo("Sales · B2C", "ben@pharmacrm.test", "Ben Cruz", "Rep · B2C MD Telesales"),
    Demo("Sales · B2C", "tess@pharmacrm.test", "Tess Aquino", "Team Lead · B2C General"),
    Demo("Sales · STC, URO", "nena@pharmacrm.test", "Nena Gutierrez", "Rep · STC MD Telesales"),
    Demo("Sales · STC, URO", "rico@pharmacrm.test", "Rico Padilla", "Rep · URO MD Telesales"),
    Demo("Sales · B&B", "ana@pharmacrm.test", "Ana Reyes", "Rep · B&B MD Telesales + B2C General"),
    Demo("Sales · B&B", "paolo@pharmacrm.test", "Paolo Mendoza", "Team Lead · B&B MD Telesales"),
    Demo("Sales · B&B", "lorna@pharmacrm.test", "Lorna Bautista", "Division Head · B&B"),
    Demo("Sales · B2B", "marlon@pharmacrm.test", "Marlon Yap", "Rep · B2B NBD"),
    Demo("Sales · B2B", "dina@pharmacrm.test", "Dina Salazar", "Rep · B2B CRR"),
    Demo("Sales · B2B", "noel@pharmacrm.test", "Noel Ramos", "Division Head · B2B"),
    Demo("Sales · HOS", "grace@pharmacrm.test", "Grace Lim", "Rep · HOS Hospital"),
    Demo("Sales · HOS", "elmer@pharmacrm.test", "Elmer Tan", "Rep · HOS Telesales"),
    Demo("Sales · HOS", "vicky@pharmacrm.test", "Vicky Ong", "Team Lead · HOS Hospital"),
    Demo("Sales · BID", "rosa@pharmacrm.test", "Rosa Ferrer", "Rep · BID Bidding"),
)
