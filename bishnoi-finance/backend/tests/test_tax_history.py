"""The registration's "On record" summary and its history of changes (added 2026-10-22):
who changed it last, and each change by the parts that changed, never the values."""

from app.models import AuditEntry

from .test_tax_api import REGISTRATION, app, ana, ben, client  # noqa: F401 (fixtures)


def setup(client, who):
    return client.get("/tax/setup", headers=who).json()


def test_a_new_registration_has_no_history(client, ben):
    s = setup(client, ben)
    assert s["history"] == [] and s["profile"]["updatedByName"] is None


def test_each_change_names_the_parts_that_changed(client, ana, ben):
    client.put("/tax/profile", json={**REGISTRATION, "registeredAddress": None}, headers=ana)
    client.put("/tax/profile", json=REGISTRATION, headers=ana)
    s = setup(client, ben)  # anyone who can see Tax sees who changed it
    assert s["profile"]["updatedByName"].startswith("Ana")
    newest, first = s["history"]
    assert newest["changed"] == ["registered address"] and newest["who"].startswith("Ana")
    assert first["changed"] == ["registered name", "TIN"]  # the rest were already what was sent
    assert newest["at"] >= first["at"]


def test_saving_it_unchanged_adds_nothing(client, ana):
    client.put("/tax/profile", json=REGISTRATION, headers=ana)
    before = setup(client, ana)
    again = client.put("/tax/profile", json=REGISTRATION, headers=ana)
    assert again.status_code == 200
    after = setup(client, ana)
    assert len(after["history"]) == len(before["history"]) == 1
    assert after["profile"]["updatedAt"] == before["profile"]["updatedAt"]


def test_an_older_save_says_only_that_it_was_saved(app, client, ana):
    # Before 2026-10-22 every save logged every part on the form, changed or not.
    with app.state.sessions() as db:
        db.add(AuditEntry(actor="ana@example.com", action="tax.profile_updated", target="Tax registration", target_type="settings",
                          fields=["branch_code", "country", "prices_include_tax", "regime", "registered_address", "registered_name", "tin", "trade_name"]))
        db.commit()
    (old,) = setup(client, ana)["history"]
    assert old["changed"] is None and old["who"] == "ana@example.com"
