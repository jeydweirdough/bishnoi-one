"""HR records on employees (2026-11-18, step 4I): labelled details and documents, read and changed only by the
company's administrators and holders of "Manage HR records"; never by anyone else, the employee included."""

from modules.platform.models import AuditEntry, HrDocument, Identity
from modules.platform.tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)

PDF = b"%PDF-1.4\n% test\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n"


def hr_role_for(client, owner_h, person_id):
    role = client.post("/identity/access/roles", json={"name": "HR"}, headers=owner_h).json()
    r = client.put(f"/identity/access/roles/{role['id']}/abilities", json={"abilities": [{"key": "hr.records"}]}, headers=owner_h)
    assert r.status_code == 200, r.text
    assert client.put(f"/identity/access/people/{person_id}/role", json={"roleId": role["id"]}, headers=owner_h).status_code == 200


def upload(client, h, person_id, data=PDF, name="contract.pdf", label="Contract", expires=""):
    return client.post(f"/identity/access/people/{person_id}/hr/documents", files={"file": (name, data, "application/octet-stream")},
                       data={"label": label, "expiresOn": expires}, headers=h)


def test_administrators_and_hr_keep_records_nobody_else(app, client, getmeds):  # noqa: F811 (fixtures)
    owner, jade, rio = getmeds["owner"]["h"], getmeds["jade"], getmeds["rio"]
    url = f"/identity/access/people/{rio['id']}/hr"
    # Before HR is given: Jade, Rio himself, are refused.
    assert client.get(url, headers=jade["h"]).status_code == 403
    assert client.get(url, headers=rio["h"]).status_code == 403
    assert client.get("/identity/me", headers=jade["h"]).json()["hrRecords"] is False
    assert client.get("/identity/me", headers=owner).json()["hrRecords"] is True

    r = client.put(url, json={"details": [{"label": "SSS no.", "value": "34-1234567-8"}, {"label": "TIN", "value": "123-456-789-000"},
                                          {"label": "Shoe size", "value": ""}]}, headers=owner)
    assert r.status_code == 200, r.text
    assert r.json()["details"] == [{"label": "SSS no.", "value": "34-1234567-8"}, {"label": "TIN", "value": "123-456-789-000"}]
    assert "SSS no." in r.json()["suggestedDetails"]

    hr_role_for(client, owner, jade["id"])
    assert client.get("/identity/me", headers=jade["h"]).json()["hrRecords"] is True
    assert client.get(url, headers=jade["h"]).json()["details"][0]["label"] == "SSS no."
    assert [p["id"] for p in client.get("/identity/access/hr/people", headers=jade["h"]).json()["people"]].count(rio["id"]) == 1
    # HR changes them too; a free label is kept.
    r = client.put(url, json={"details": [{"label": "TIN", "value": "123-456-789-000"}, {"label": "Locker", "value": "B-12"}]}, headers=jade["h"])
    assert r.status_code == 200 and [d["label"] for d in r.json()["details"]] == ["TIN", "Locker"]
    doc = upload(client, jade["h"], rio["id"], expires="2027-01-31")
    assert doc.status_code == 201, doc.text
    assert doc.json()["contentType"] == "application/pdf" and doc.json()["expiresOn"] == "2027-01-31"
    opened = client.get(f"{url}/documents/{doc.json()['id']}", headers=owner)
    assert opened.status_code == 200 and opened.content == PDF
    assert opened.headers["cache-control"] == "no-store" and opened.headers["content-disposition"].startswith("inline")

    # Rio still can't see his own, nor upload, nor open; the plain employee API refuses the same.
    assert client.get(url, headers=rio["h"]).status_code == 403
    assert client.get(f"{url}/documents/{doc.json()['id']}", headers=rio["h"]).status_code == 403
    assert upload(client, rio["h"], rio["id"]).status_code == 403
    assert client.get("/identity/access/hr/people", headers=rio["h"]).status_code == 403
    # Not the employee list itself: HR isn't an administrator.
    assert client.get("/identity/access", headers=jade["h"]).status_code == 403

    assert client.delete(f"{url}/documents/{doc.json()['id']}", headers=jade["h"]).status_code == 204
    assert client.get(url, headers=owner).json()["documents"] == []

    # The audit log names labels, never values.
    with app.state.sessions() as db:
        lines = db.query(AuditEntry).filter(AuditEntry.action.like("hr.%")).all()
        actions = {e.action for e in lines}
        assert {"hr.details_changed", "hr.document_added", "hr.document_opened", "hr.document_removed", "hr.records_viewed"} <= actions
        text = " ".join(f"{e.target} {e.fields}" for e in lines)
        assert "SSS no." in text and "Locker" in text
        assert "34-1234567" not in text and "123-456" not in text and "B-12" not in text


def test_details_and_files_are_checked(client, getmeds):  # noqa: F811 (fixtures)
    owner, rio = getmeds["owner"]["h"], getmeds["rio"]
    url = f"/identity/access/people/{rio['id']}/hr"
    assert client.put(url, json={"details": [{"label": "TIN", "value": "1"}, {"label": "tin", "value": "2"}]}, headers=owner).status_code == 422
    assert client.put(url, json={"details": [{"label": "x" * 61, "value": "1"}]}, headers=owner).status_code == 422
    assert client.put(url, json={"details": [{"label": "Note", "value": "x" * 501}]}, headers=owner).status_code == 422
    assert client.put(url, json={"details": [{"label": None, "value": "orphan"}]}, headers=owner).status_code == 422
    assert client.put(url, json={"details": [{"label": f"L{i}", "value": "v"} for i in range(51)]}, headers=owner).status_code == 422
    # Types by their bytes, not their names.
    assert upload(client, owner, rio["id"], data=b"MZ\x90\x00 not a pdf", name="contract.pdf").status_code == 415
    assert upload(client, owner, rio["id"], data=b"PK\x03\x04 broken", name="x.docx").status_code == 415
    assert upload(client, owner, rio["id"], data=b"\x89PNG\r\n\x1a\n" + b"0" * 10, name="id.png", label="Valid ID").json()["contentType"] == "image/png"
    assert upload(client, owner, rio["id"], data=b"%PDF-" + b"0" * 10_000_001).status_code == 413
    assert upload(client, owner, rio["id"], label="").status_code == 422
    assert upload(client, owner, rio["id"], expires="next year").status_code == 422
    # Someone at another company, or nobody, isn't found.
    assert client.get("/identity/access/people/nobody/hr", headers=owner).status_code == 404


def test_erasing_an_employee_takes_their_hr_records(app, client, getmeds):  # noqa: F811 (fixtures)
    owner, rio = getmeds["owner"]["h"], getmeds["rio"]
    client.put(f"/identity/access/people/{rio['id']}/hr", json={"details": [{"label": "TIN", "value": "123"}]}, headers=owner)
    assert upload(client, owner, rio["id"]).status_code == 201
    assert client.delete(f"/identity/access/people/{rio['id']}", headers=owner).status_code == 200
    # In the recycle bin they're kept, to restore.
    with app.state.sessions() as db:
        assert db.query(HrDocument).filter_by(identity_id=rio["id"]).count() == 1
    assert client.post(f"/identity/access/people/{rio['id']}/erase", json={"email": "rio@getmeds.test"}, headers=owner).status_code == 204
    with app.state.sessions() as db:
        assert db.query(HrDocument).filter_by(identity_id=rio["id"]).count() == 0
        assert db.get(Identity, rio["id"]) is None
