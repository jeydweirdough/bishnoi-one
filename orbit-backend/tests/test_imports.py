"""Bringing a spreadsheet in.

The sheets these tests use are deliberately awkward — odd column names, a blank
row, a price with a peso sign and commas, a duplicate code — because that is
what a real one looks like. Orbit has to read it as it is.
"""

import io
import json

import pytest
from openpyxl import Workbook


def workbook(rows: list[list]) -> bytes:
    book = Workbook()
    page = book.active
    for row in rows:
        page.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def upload(client, headers, path: str, data: bytes, name: str = "products.xlsx", mapping: dict | None = None):
    files = {"file": (name, data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    body = {"mapping": json.dumps(mapping)} if mapping is not None else None
    return client.post(path, files=files, data=body, headers=headers)


MESSY = [
    ["Item Code", "Product Name", "Packing", "Patient's Price", "Generic name", "Notes for us"],
    ["VIT-C-500", "Vitamin C 500 mg", "Box of 100", "₱ 1,250.00", "Ascorbic acid", "fast mover"],
    [],
    ["ZINC-20", "Zinc 20 mg", "Box of 30", "450", "Zinc sulfate", ""],
]


def test_orbit_reads_the_sheet_you_already_have(client, as_):
    """No template: it says what it found and guesses which column is which."""
    r = upload(client, as_("carmen"), "/admin/data/products/columns", workbook(MESSY))
    assert r.status_code == 200, r.text
    found = r.json()
    assert found["columns"] == ["Item Code", "Product Name", "Packing", "Patient's Price", "Generic name", "Notes for us"]
    assert found["rowCount"] == 2  # the blank row is not a row

    guessed = {f["key"]: f["column"] for f in found["fields"]}
    assert guessed["code"] == "Item Code"
    assert guessed["name"] == "Product Name"
    assert guessed["unit"] == "Packing"
    assert guessed["price:patient"] == "Patient's Price"
    assert guessed["field:generic_name"] == "Generic name"


def test_nothing_is_written_until_the_review_is_accepted(client, as_):
    carmen = as_("carmen")
    mapping = {"code": "Item Code", "name": "Product Name", "unit": "Packing", "price:patient": "Patient's Price"}

    dry = upload(client, carmen, "/admin/data/products/check", workbook(MESSY), mapping=mapping).json()
    assert dry["counts"]["new"] == 2 and dry["wouldWrite"] == 2
    assert dry["unusedColumns"] == ["Generic name", "Notes for us"]
    assert [c["code"] for c in client.get("/inventory/products", headers=as_("iris")).json() if c["code"] == "VIT-C-500"] == []

    done = upload(client, carmen, "/admin/data/products/import", workbook(MESSY), mapping=mapping).json()
    assert done["counts"]["new"] == 2
    made = next(p for p in client.get("/inventory/products", headers=as_("iris")).json() if p["code"] == "VIT-C-500")
    assert made["name"] == "Vitamin C 500 mg"
    assert made["unit"] == "Box of 100"
    assert made["prices"]["patient"] == 125_000  # the peso sign and the comma are not part of the number


def test_running_it_again_changes_nothing(client, as_):
    carmen = as_("carmen")
    mapping = {"code": "Item Code", "name": "Product Name", "unit": "Packing", "price:patient": "Patient's Price"}
    upload(client, carmen, "/admin/data/products/import", workbook(MESSY), mapping=mapping)
    again = upload(client, carmen, "/admin/data/products/check", workbook(MESSY), mapping=mapping).json()
    assert again["counts"] == {"new": 0, "changed": 0, "same": 2, "refused": 0}


def test_a_changed_price_shows_as_changed_not_new(client, as_):
    carmen = as_("carmen")
    mapping = {"code": "Item Code", "name": "Product Name", "unit": "Packing", "price:patient": "Patient's Price"}
    upload(client, carmen, "/admin/data/products/import", workbook(MESSY), mapping=mapping)
    dearer = [MESSY[0], [MESSY[1][0], MESSY[1][1], MESSY[1][2], "1,400", "", ""], MESSY[3]]
    dry = upload(client, carmen, "/admin/data/products/check", workbook(dearer), mapping=mapping).json()
    assert dry["counts"]["changed"] == 1 and dry["counts"]["same"] == 1


def test_bad_rows_are_named_and_the_rest_still_go(client, as_):
    carmen = as_("carmen")
    rows = [
        ["Item Code", "Product Name", "Patient's Price"],
        ["GOOD-1", "A real product", "100"],
        ["", "No code here", "100"],
        ["GOOD-1", "The same code twice", "100"],
        ["BAD-PRICE", "Priced in words", "about a hundred"],
    ]
    mapping = {"code": "Item Code", "name": "Product Name", "price:patient": "Patient's Price"}
    dry = upload(client, carmen, "/admin/data/products/check", workbook(rows), mapping=mapping).json()
    assert dry["counts"] == {"new": 1, "changed": 0, "same": 0, "refused": 3}
    why = {r["line"]: r["why"] for r in dry["rows"] if r["outcome"] == "refused"}
    assert "No product code" in why[3]
    assert "twice" in why[4]
    assert "isn't a price" in why[5]


def test_a_price_type_this_company_does_not_keep_is_refused(client, as_):
    carmen = as_("carmen")
    rows = [["Code", "Name", "Wholesale"], ["W-1", "Something", "100"]]
    mapping = {"code": "Code", "name": "Name", "price:wholesale": "Wholesale"}
    dry = upload(client, carmen, "/admin/data/products/check", workbook(rows), mapping=mapping).json()
    assert dry["counts"]["refused"] == 1
    assert "price type called wholesale" in dry["rows"][0]["why"]


def test_a_csv_works_too(client, as_):
    csv = "Code,Name,Patient's Price\nCSV-1,From a CSV,99.50\n".encode()
    r = upload(client, as_("carmen"), "/admin/data/products/columns", csv, name="products.csv")
    assert r.status_code == 200
    assert r.json()["columns"] == ["Code", "Name", "Patient's Price"]


def test_something_that_is_not_a_spreadsheet(client, as_):
    r = upload(client, as_("carmen"), "/admin/data/products/columns", b"not a spreadsheet", name="notes.txt")
    assert r.status_code == 422


def test_only_the_owner_moves_data_in_or_out(client, as_):
    lorna = as_("lorna")
    assert client.get("/admin/data/export", headers=lorna).status_code == 403
    assert upload(client, lorna, "/admin/data/products/columns", workbook(MESSY)).status_code == 403


def test_the_owner_downloads_the_whole_company(client, as_):
    r = client.get("/admin/data/export", headers=as_("carmen"))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    import zipfile

    archive = zipfile.ZipFile(io.BytesIO(r.content))
    assert "manifest.json" in archive.namelist()
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["company"]["slug"] == "getmeds"
    assert manifest["tables"]["products"] >= 1
