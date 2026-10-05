"""CLIDP on products (app/clidp.py): quotes and deals warn about a product whose
certificate has run out, or isn't on file where the division needs one."""

from datetime import date, timedelta

from sqlalchemy import select

from app import clidp
from app.models import Company, Product, Team, User
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, ids, line, preview  # noqa: F401 (fixtures)

PAST = (date.today() - timedelta(days=1)).isoformat()
LATER = (date.today() + timedelta(days=90)).isoformat()


def set_clidp(app, code: str, **extra) -> None:
    with app.state.sessions() as db:
        product = db.scalar(select(Product).where(Product.code == code))
        product.extra = {**(product.extra or {}), **extra}
        db.commit()


def test_a_quote_warns_of_a_clidp_that_ran_out(app, client, crew, ids):
    set_clidp(app, "AMX-500", x_clidp_number="CLIDP-1", x_clidp_valid_until=PAST)
    set_clidp(app, "CTZ-10", x_clidp_number="CLIDP-2", x_clidp_valid_until=LATER)
    acme = company(client, crew["ria"])
    r = preview(client, crew["ria"], acme, [line(ids["AMX-500"]), line(ids["CTZ-10"])])
    assert r.status_code == 200, r.text
    warned = r.json()["clidpWarnings"]
    assert len(warned) == 1 and "ran out" in warned[0]


def test_missing_clidps_matter_only_where_the_division_needs_them(app):
    with app.state.sessions() as db:
        bid, rx = Team(name="BID"), Team(name="STC")
        db.add_all([bid, rx, Product(code="P1", name="Generic One"), Product(code="P2", name="Generic Two", extra={clidp.NUMBER: "C-9", clidp.VALID_UNTIL: LATER})])
        db.flush()
        owner = db.scalar(select(User))
        today = date.today().isoformat()
        for_bid = Company(name="DOH IV-A", owner_id=owner.id, team_id=bid.id)
        for_rx = Company(name="Dr. Lim", owner_id=owner.id, team_id=rx.id)
        db.add_all([for_bid, for_rx])
        db.flush()
        assert clidp.warnings(db, ["P1", "P2"], for_bid, today) == ["Generic One: no CLIDP on file."]
        assert clidp.warnings(db, ["P1", "P2"], for_rx, today) == []
