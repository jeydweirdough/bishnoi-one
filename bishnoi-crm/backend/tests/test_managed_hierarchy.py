"""Organisational heads see their subtree, without exposing peer divisions."""

from sqlalchemy import select

from app.access import access_of
from app.models import Company, Team, User
from app.scope import reachable_people, reaches, within
from tests.conftest import role_id


def test_department_division_and_team_heads_have_separate_reach(app):
    with app.state.sessions() as db:
        manager = role_id(db, "Manager")
        salesperson = role_id(db, "Salesperson")

        def person(name, role=manager, **kwargs):
            user = User(email=f"{name}@example.com", full_name=name,
                        password_hash="unused", role_id=role, **kwargs)
            db.add(user)
            db.flush()
            return user

        head = person("department")
        javed = person("javed")
        coach = person("coach")
        peer = person("peer")
        department = Team(name="Sales", manager_id=head.id)
        db.add(department)
        db.flush()
        rx = Team(name="Prescription", parent_id=department.id, manager_id=javed.id)
        other = Team(name="Other division", parent_id=department.id, manager_id=peer.id)
        db.add_all([rx, other])
        db.flush()
        team = Team(name="B2C", parent_id=rx.id, manager_id=coach.id)
        db.add(team)
        db.flush()
        leaf = Team(name="Field", parent_id=team.id)
        db.add(leaf)
        db.flush()
        head.team_id = department.id
        # Shared parent membership must not authorize the other division.
        javed.team_id = department.id
        coach.team_id = team.id
        peer.team_id = other.id
        worker = person("worker", salesperson, team_id=leaf.id)
        outsider = person("outsider", salesperson, team_id=other.id)
        assistant = person("assistant", salesperson, assistant_of_id=javed.id)
        linked = person("linked", salesperson, team_id=other.id, reports_to_id=javed.id)
        records = [Company(name=p.full_name, owner_id=p.id, team_id=p.team_id)
                   for p in (worker, outsider, linked)]
        db.add_all(records)
        db.commit()

        def names(user):
            return {p.full_name for p in reachable_people(db, access_of(user))}

        assert {"department", "javed", "coach", "peer", "worker", "outsider"} <= names(head)
        assert names(javed) == {"javed", "coach", "worker", "linked"}
        assert access_of(javed).team_ids == frozenset({rx.id, team.id, leaf.id})
        assert not access_of(javed).runs(department.id)
        assert names(coach) == {"coach", "worker"}
        assert names(worker) == {"worker"}
        assert names(assistant) == {"assistant", "javed", "coach", "worker", "linked"}
        assert access_of(assistant).permissions == access_of(worker).permissions
        for user in (javed, assistant):
            access = access_of(user)
            assert {c.name for c in db.scalars(within(select(Company), Company, access))} == {"worker", "linked"}
            assert reaches(records[0], access)
            assert not reaches(records[1], access)

        # Revoking the head assignment removes subtree access on the next request.
        rx.manager_id = None
        db.commit()
        javed_id = javed.id
    with app.state.sessions() as db:
        access = access_of(db.get(User, javed_id))
        assert {p.full_name for p in reachable_people(db, access)} == {"javed", "linked"}
