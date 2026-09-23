"""Imports: a spreadsheet's columns mapped onto products or people, checked
row by row, then saved."""

import io

from openpyxl import Workbook

from tests.test_customers import crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue  # noqa: F401 (a fixture)


def xlsx(rows) -> bytes:
    book = Workbook()
    for row in rows:
        book.active.append(row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def read(client, headers, kind, name, data):
    return client.post(f"/imports/{kind}/read", files={"file": (name, data)}, headers=headers)


PRODUCTS = [
    ["Item Code", "Brand Name", "Generic", "UOM", "Patient Price", "Status", "Something else"],
    ["amx-500", "Amoxil", "Amoxicillin", "box of 100", "1,500.00", "Active", "x"],
    ["NEW-1", "Newcillin", "Newcillin", "box", "₱ 250", "yes", "y"],
    ["NEW-2", "", "", "box", "100", "", ""],  # a new product without a name
    ["NEW-3", "Pricey", "", "box", "lots", "", ""],  # not an amount
]


def test_products_are_read_mapped_checked_and_imported(client, crew, ana, catalogue):
    assert read(client, crew["ria"], "products", "p.xlsx", xlsx(PRODUCTS)).status_code == 403  # salespeople don't import
    r = read(client, ana, "products", "p.xlsx", xlsx(PRODUCTS))
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["headers"][:2] == ["Item Code", "Brand Name"] and len(got["rows"]) == 4
    m = got["mapping"]
    assert (m["code"], m["name"], m["genericName"], m["unit"], m["price:PATIENT"], m["isActive"]) == (0, 1, 2, 3, 4, 5)

    body = {"mapping": m, "rows": got["rows"], "dryRun": True}
    check = client.post("/imports/products", json=body, headers=ana).json()
    assert (check["added"], check["updated"]) == (1, 1)
    assert [p["row"] for p in check["problems"]] == [4, 5]
    assert client.get("/products?q=newcillin", headers=ana).json()["total"] == 0  # a check saves nothing

    done = client.post("/imports/products", json={**body, "dryRun": False}, headers=ana).json()
    assert (done["added"], done["updated"], len(done["problems"])) == (1, 1, 2)
    products = {p["code"]: p for p in client.get("/products?limit=500", headers=ana).json()["items"]}
    assert products["AMX-500"]["prices"]["PATIENT"] == 150000 and products["AMX-500"]["prices"]["TRADE"] == 118000  # the rest kept
    assert (products["NEW-1"]["name"], products["NEW-1"]["prices"], products["NEW-1"]["isActive"]) == ("Newcillin", {"PATIENT": 25000}, True)
    assert "NEW-2" not in products and "NEW-3" not in products


def test_people_are_imported_with_their_roles_and_teams(client, crew, ana):
    rows = [
        ["E-mail Address", "Employee Name", "Position", "Division"],
        ["joy@example.com", "Joy Lim", "Salesperson", "North"],
        ["kim@example.com", "Kim Uy", "", "Pharma East"],  # no role: a salesperson; a new team
        ["RIA@example.com", "Ria Santos", "Team Lead", ""],  # already here: updated
        ["bad-email", "Nobody", "", ""],
        ["zed@example.com", "Zed", "Wizard", ""],  # no such role
    ]
    csv = "\n".join(",".join(r) for r in rows).encode()
    assert read(client, crew["max"], "people", "people.csv", csv).status_code == 403  # admin.users only
    got = read(client, ana, "people", "people.csv", csv).json()
    m = got["mapping"]
    assert (m["email"], m["fullName"], m["role"], m["team"]) == (0, 1, 2, 3)
    body = {"mapping": m, "rows": got["rows"], "dryRun": False}
    assert "first password" in client.post("/imports/people", json={**body, "password": "short"}, headers=ana).json()["detail"]
    no_password = client.post("/imports/people", json=body, headers=ana).json()
    assert no_password["added"] == 0 and any("first password" in p["message"] for p in no_password["problems"])
    done = client.post("/imports/people", json={**body, "password": "welcome to orbit"}, headers=ana).json()
    assert (done["added"], done["updated"]) == (2, 1)
    assert sorted(p["row"] for p in done["problems"]) == [5, 6]
    users = {u["email"]: u for u in client.get("/admin/users", headers=ana).json()}
    assert (users["joy@example.com"]["role"]["name"], users["joy@example.com"]["team"]["name"]) == ("Salesperson", "North")
    assert users["kim@example.com"]["team"]["name"] == "Pharma East"
    assert users["ria@example.com"]["role"]["name"] == "Team Lead"
    assert client.post("/auth/login", json={"email": "joy@example.com", "password": "welcome to orbit"}).status_code == 200
