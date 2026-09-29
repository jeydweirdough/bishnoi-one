"""The first administrator, from the settings (FIRST_ADMIN_EMAIL, _NAME,
_PASSWORD), for a database nobody can run the users tool against. Only ever
into a database with no accounts: once anyone exists, the settings are ignored.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import User
from app.security import check_password_rules, hash_password

log = logging.getLogger("finance.first_admin")


def make_first_admin(sessions: sessionmaker[Session], settings: Settings) -> None:
    if not settings.first_admin_email or settings.first_admin_password is None:
        return
    with sessions() as db:
        if db.scalar(select(func.count()).select_from(User)):
            return
        password = settings.first_admin_password.get_secret_value()
        problem = check_password_rules(password)
        if problem:
            log.error("FIRST_ADMIN_PASSWORD not used: %s", problem)
            return
        user = User(
            email=settings.first_admin_email.strip().lower(),
            full_name=settings.first_admin_name.strip() or "Administrator",
            password_hash=hash_password(password),
            role="admin",
        )
        db.add(user)
        db.commit()
        log.warning("Made the first administrator, %s. Remove FIRST_ADMIN_PASSWORD now.", user.email)
