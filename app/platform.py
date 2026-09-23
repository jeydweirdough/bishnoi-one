"""Developer Admins: the tier above every company.

Orbit runs many companies. Each one has its own Admins, who run it — its people,
its roles, its teams, its business rules — and who cannot reach anything outside
it. That is the point of the wall (app/tenancy.py).

Somebody has to be able to reach across it. When a company's link to another
application is wrong, when its last Admin is locked out, when its record itself
is broken, the person who fixes it is not in that company at all. That is the
Developer Admin: one tier, above all of them.

**It is deliberately not a role.** A company's Admin edits the permission matrix,
so anything granted through a role is something they could grant themselves —
and a company being able to promote its own staff to reach every *other* company
would make the wall decoration. Membership of `platform_admins` is set outside
any company (`python -m app.platform`), which is the only reason it means
anything.

Inside whichever company they are looking at, a Developer Admin holds RECOVER
(app/modules.py): the company record, its accounts, its app links and its audit
log. Not its prices, not its roles. Running a company stays the Admin's job even
when the Developer Admin is the one keeping it running.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization, PlatformAdmin, Profile
from app.tenancy import all_companies


def is_developer_admin(db: Session, user_id: str) -> bool:
    """`platform_admins` has no org_id, so it is read outside the wall and means
    the same thing whichever company the session is walled to."""
    return db.get(PlatformAdmin, user_id) is not None


def developer_admins(db: Session) -> list[Profile]:
    rows = db.scalars(select(PlatformAdmin)).all()
    with all_companies(db):
        people = {p.id: p for p in db.scalars(select(Profile).where(Profile.id.in_([r.user_id for r in rows])))}
    return sorted((people[r.user_id] for r in rows if r.user_id in people), key=lambda p: p.full_name.casefold())


def every_company(db: Session) -> list[Organization]:
    """Every company on the platform, whatever this session is walled to."""
    with all_companies(db):
        return list(db.scalars(select(Organization).order_by(Organization.name)))


def company(db: Session, org_id: str) -> Organization | None:
    with all_companies(db):
        return db.get(Organization, org_id)


def make_developer_admin(db: Session, email: str) -> Profile | None:
    """Promotes an existing account. None if there is no such person.

    Deliberately not an API route a company's screens can reach: a Developer
    Admin is made from outside every company, or by another Developer Admin."""
    with all_companies(db):
        person = db.scalar(select(Profile).where(Profile.email == email.lower()))
        if person is None:
            return None
        if db.get(PlatformAdmin, person.id) is None:
            db.add(PlatformAdmin(user_id=person.id))
            db.commit()
        return person


def drop_developer_admin(db: Session, email: str) -> bool:
    with all_companies(db):
        person = db.scalar(select(Profile).where(Profile.email == email.lower()))
        row = db.get(PlatformAdmin, person.id) if person else None
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


def main(argv: list[str] | None = None) -> int:
    """`python -m app.platform --grant someone@example.com`"""
    import argparse

    from app.config import get_settings
    from app.db import make_engine, make_sessions

    parser = argparse.ArgumentParser(prog="python -m app.platform", description=__doc__.split("\n")[0])
    parser.add_argument("--grant", metavar="EMAIL", help="make this account a Developer Admin")
    parser.add_argument("--revoke", metavar="EMAIL", help="stop this account being one")
    parser.add_argument("--list", action="store_true", help="who they are")
    args = parser.parse_args(argv)

    sessions = make_sessions(make_engine(get_settings().database_url))
    with sessions() as db:
        if args.grant:
            person = make_developer_admin(db, args.grant)
            print(f"{args.grant} is a Developer Admin." if person else f"No account for {args.grant}.")
            if person is None:
                return 1
        if args.revoke:
            print(f"{args.revoke} is no longer a Developer Admin." if drop_developer_admin(db, args.revoke) else f"{args.revoke} was not one.")
        if args.list or not (args.grant or args.revoke):
            people = developer_admins(db)
            print("Developer Admins:" if people else "No Developer Admins yet.")
            for p in people:
                print(f"  {p.full_name} <{p.email}>")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
