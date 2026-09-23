"""The platform: every company on Orbit, and putting a new one on it.

This is the Developer Admin's own screen, and the only router that works with no
company at all. Everything else in Orbit belongs to one.

Taking a company on is the job this exists for: a name, a short name, the money
and time it works in, and the first person who will run it. Orbit seeds the rest
-- divisions, teams, roles, price types, order settings -- from the template, so
the company has something to open rather than a blank system. Its Admin changes
every bit of it afterwards, which is the point of Settings.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import owns_company
from app.deps import DB, CurrentUser
from app.models import Membership, Organization, Profile
from app.modules import ALL_MODULES
from app.platform import company, every_company, is_developer_admin
from app.schemas import NewCompanyIn
from app.scope import slugify
from app.tenancy import all_companies, set_company

router = APIRouter(prefix="/platform", tags=["platform"])


def require_developer(user: CurrentUser, db: DB) -> None:
    """The tier above every company. Not a role, so nothing a company does can
    reach this router (app/platform.py)."""
    if not is_developer_admin(db, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is for developer admins.")


guard = Depends(require_developer)


def company_out(db: Session, org: Organization) -> dict:
    with all_companies(db):
        people = db.scalar(
            select(Membership).where(Membership.org_id == org.id, Membership.status == "active").limit(1)
        )
        count = len(
            db.scalars(select(Membership.user_id).where(Membership.org_id == org.id, Membership.status == "active")).all()
        )
    return {
        "id": org.id,
        "slug": org.slug,
        "name": org.name,
        "brandName": org.brand_name,
        "status": org.status,
        "currency": org.currency,
        "minorUnits": org.minor_units,
        "locale": org.locale,
        "timezone": org.timezone,
        "orderPrefix": org.order_prefix,
        "template": org.template,
        "createdAt": org.created_at.isoformat(),
        "peopleCount": count,
        # A company with nobody in it cannot be signed into: it needs its first Admin.
        "isReady": people is not None,
    }


@router.get("/companies", dependencies=[guard])
def list_companies(db: DB) -> dict:
    return {"companies": [company_out(db, o) for o in every_company(db)]}


@router.post("/companies", status_code=status.HTTP_201_CREATED, dependencies=[guard])
def create_company(body: NewCompanyIn, db: DB) -> dict:
    """A company joins the platform, with the person who will run it.

    Seeded from the template so it opens to a working system; its Admin changes
    all of it in Settings. The first person is given the Admin role, because a
    company nobody can administer is a company nobody can set up."""
    # Imported here: app.seed pulls in a great deal, and this is the one route
    # that needs it.
    from app.seed import add_person, seed_reference

    slug = slugify(body.slug or body.name)[:40].strip("-")
    if not slug:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Give it a name with letters or numbers in it.")

    with all_companies(db):
        taken = db.scalar(select(Organization).where(Organization.slug == slug))
        if taken is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, f"There is already a company at “{slug}”.")
        existing = db.scalar(select(Profile).where(Profile.email == body.admin_email.lower()))
        org = Organization(
            slug=slug,
            name=body.name,
            brand_name=body.brand_name or body.name,
            template=body.template,
            currency=body.currency,
            minor_units=body.minor_units,
            locale=body.locale,
            timezone=body.timezone,
            order_prefix=body.order_prefix or slug[:2].upper(),
        )
        db.add(org)
        db.commit()

    # Everything the company opens to: its divisions, teams, roles, price types,
    # order settings and app links.
    seed_reference(db, org.id)
    add_person(
        db,
        body.admin_email.lower(),
        body.admin_name,
        body.admin_password,
        [("admin", ALL_MODULES, None, None)],
    )
    with all_companies(db):
        fresh = db.get(Organization, org.id)
    return {
        "company": company_out(db, fresh),
        "admin": {
            "email": body.admin_email.lower(),
            "name": body.admin_name,
            # Somebody already on Orbit keeps the password they have; the one
            # typed here is only used when the account is new.
            "joinedExistingAccount": existing is not None,
        },
    }


@router.get("/companies/{org_id}/people", dependencies=[guard])
def company_people(org_id: str, db: DB) -> dict:
    """Who is in this company, whoever runs it first.

    This is how a Developer Admin finds the person to look through: the Admins,
    then everybody else. Their access is described, not their records."""
    from app.access import access_for_everyone

    org = company(db, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such company.")
    set_company(db, org_id)
    people = []
    for user_id, (profile, access) in access_for_everyone(db).items():
        modules = sorted({m for m, _ in access.grants})
        people.append(
            {
                "id": user_id,
                "email": profile.email,
                "fullName": profile.full_name,
                "isAdmin": access.manage_settings,
                "isOwner": owns_company(db, user_id),
                # What they would see: the modules they hold anything in.
                "moduleCount": len(modules),
                "isDeveloperAdmin": is_developer_admin(db, user_id),
            }
        )
    people.sort(key=lambda p: (not p["isOwner"], not p["isAdmin"], p["fullName"].casefold()))
    return {"company": company_out(db, org), "people": people}


@router.patch("/companies/{org_id}", dependencies=[guard])
def set_company_status(org_id: str, on: bool, db: DB) -> dict:
    """Switches a company off, or back on. Off means nobody in it can sign in;
    nothing of theirs is deleted."""
    with all_companies(db):
        org = db.get(Organization, org_id)
        if org is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such company.")
        org.status = "active" if on else "suspended"
        db.commit()
        fresh = db.get(Organization, org_id)
    return {"company": company_out(db, fresh)}

