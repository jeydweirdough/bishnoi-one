"""Taking a company's world out, and putting it back.

An export is the only copy of a company that exists outside the running
system, so it is held to three things here: it holds everything that company
has, it holds nothing of anybody else's, and it goes back in. The last one is
what makes the first two worth anything, so the round trip is counted row by
row and record by record.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select

from app.config import API_DIR
from app.db import make_engine
from app.models import ApiKey, Base, Organization, Product
from app.scope import Scope
from app.seed import DEMO_PASSWORD, add_person
from app.store.files import FileStore
from app.store.local import LocalBackend
from app.store.query import Query
from app.store.records import Records
from app.tenancy import FIRST_ORG_ID, set_company
from app.tools import backup, export
from app.tools.export import RECORD_TYPES, World, company_scopes, company_tables
from tests.conftest import ACME, ACME_CUSTOMER, ACME_PRODUCT, PDF, customer_id, post_quote, product_ids

# A third company with something in it already, for the restore that has to be told twice.
SPARE = "00000000-0000-4000-8000-00000000005a"


@pytest.fixture
def settings(settings, tmp_path):
    """The export reads uploaded files from disk, so this test's files go in this test's folder."""
    return settings.model_copy(update={"files_path": tmp_path / "files"})


@pytest.fixture
def files(settings):
    return FileStore(settings.files_path)


@pytest.fixture
def world(app, records, settings) -> World:
    return World(app.state.sessions.kw["bind"], records, settings.files_path)


def letter_quote(client, as_) -> dict:
    """Ana's B2C quote for Maria Lopez, with a guarantee letter uploaded: the one file the demo company has."""
    ana = as_("ana")
    quote = {
        "priceType": "patient",
        "payer": "dswd",
        "lines": [{"productId": product_ids(client, ana, "b2c")["ASC-500"], "quantity": 2}],
        "letter": {"number": "DSWD-7", "issuedOn": "2026-09-10", "amountCentavos": 96000},
    }
    r = post_quote(client, ana, "b2c", customer_id(client, ana, "b2c", "Maria Lopez"), quote, letter=PDF)
    assert r.status_code == 201, r.text
    return r.json()


def row_counts(world: World, org_id: str) -> dict[str, int]:
    with world.engine.connect() as connection:
        return {
            t.name: connection.scalar(select(func.count()).select_from(t).where(t.c.org_id == org_id))
            for t in company_tables()
        }


def every_scope(world: World, org_id: str) -> frozenset[Scope]:
    with world.engine.connect() as connection:
        return company_scopes(connection, org_id)


def record_counts(world: World, org_id: str) -> dict[str, int]:
    records = world.records.for_org(org_id)
    return {doc_type: records.count(Query(doc_type, every_scope(world, org_id))) for doc_type in RECORD_TYPES}


def company_id(world: World, slug: str) -> str | None:
    with world.engine.connect() as connection:
        return connection.scalar(select(Organization.__table__.c.id).where(Organization.__table__.c.slug == slug))


def profile_id(world: World, email: str) -> str | None:
    profiles = Base.metadata.tables["profiles"]
    with world.engine.connect() as connection:
        return connection.scalar(select(profiles.c.id).where(profiles.c.email == email))


def memberships_of(world: World, user_id: str) -> set[str]:
    memberships = Base.metadata.tables["memberships"]
    with world.engine.connect() as connection:
        return set(connection.scalars(select(memberships.c.org_id).where(memberships.c.user_id == user_id)))


def lines(archive: ZipFile, name: str) -> list[dict]:
    return [json.loads(line) for line in archive.read(name).splitlines() if line.strip()]


def jsonl_text(archive: ZipFile) -> str:
    return "\n".join(archive.read(n).decode("utf-8") for n in archive.namelist() if n.endswith(".jsonl"))


# --- what an export holds ---------------------------------------------------------------


def test_an_export_holds_the_companys_tables_records_and_files(client, as_, world, tmp_path):
    letter_quote(client, as_)
    out = tmp_path / "getmeds.zip"
    assert export.main(["--org", "getmeds", "--out", str(out)], world=world) == 0

    expected = row_counts(world, FIRST_ORG_ID)
    with ZipFile(out) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        customers = lines(archive, "records/customer.jsonl")
        products = lines(archive, "tables/products.jsonl")
        letters = [n for n in names if n.startswith("files/")]
        letter_bytes = archive.read(letters[0])

    assert manifest["company"] == {"id": FIRST_ORG_ID, "slug": "getmeds", "name": "Getmeds"}
    assert manifest["formatVersion"] == 1 and manifest["takenAt"].endswith("Z")
    # Every table, every record type and the uploaded letter are all in there, and the manifest counts them right.
    assert {f"tables/{t.name}.jsonl" for t in company_tables()} <= names
    assert {f"records/{t}.jsonl" for t in RECORD_TYPES} <= names
    people = expected["memberships"]
    assert manifest["tables"] == {
        **expected,
        "organizations": 1,
        "profiles": people,
        "local_credentials": people,
        "profile_photos": 0,
    }
    assert manifest["records"] == record_counts(world, FIRST_ORG_ID)
    assert manifest["files"] == len(letters) == 1 and letter_bytes == PDF
    assert "Dr. Alma Dizon" in {c["name"] for c in customers}
    assert "AMOX-500" in {p["code"] for p in products}
    assert manifest["skippedTables"] == ["sessions", "sso_codes"]


def test_an_export_holds_nothing_of_another_company(client, as_, acme, world, tmp_path):
    """Acme is next door with its own people, customer and product. Neither export may mention the other."""
    getmeds, acme_zip = tmp_path / "getmeds.zip", tmp_path / "acme.zip"
    assert export.main(["--org", "getmeds", "--out", str(getmeds)], world=world) == 0
    assert export.main(["--org", "acme", "--out", str(acme_zip)], world=world) == 0

    with ZipFile(getmeds) as archive:
        ours = jsonl_text(archive)
        rows = [row for t in company_tables() for row in lines(archive, f"tables/{t.name}.jsonl")]
        records = [doc for t in RECORD_TYPES for doc in lines(archive, f"records/{t}.jsonl")]
    for mark in (ACME, ACME_CUSTOMER, ACME_PRODUCT, "acme.test", "Olga Ortiz", "Rick Ramos"):
        assert mark not in ours
    assert {row["org_id"] for row in rows} == {FIRST_ORG_ID}
    assert {doc["orgId"] for doc in records} == {FIRST_ORG_ID}

    with ZipFile(acme_zip) as archive:
        theirs = jsonl_text(archive)
        rows = [row for t in company_tables() for row in lines(archive, f"tables/{t.name}.jsonl")]
        records = [doc for t in RECORD_TYPES for doc in lines(archive, f"records/{t}.jsonl")]
    for mark in (FIRST_ORG_ID, "pharmacrm.test", "Dr. Alma Dizon", "AMOX-500", "Ana Reyes"):
        assert mark not in theirs
    assert {row["org_id"] for row in rows} == {ACME}
    assert {doc["orgId"] for doc in records} == {ACME}
    assert ACME_CUSTOMER in {doc["name"] for doc in records}


def test_an_export_of_every_company_keeps_them_in_their_own_folders(client, acme, world, tmp_path):
    out = tmp_path / "everything.zip"
    assert export.main(["--all-companies", "--out", str(out)], world=world) == 0
    with ZipFile(out) as archive:
        top = json.loads(archive.read("manifest.json"))
        names = set(archive.namelist())
        acme_customers = lines(archive, "companies/acme/records/customer.jsonl")
    assert top["companies"] == ["acme", "getmeds"]
    assert {"companies/getmeds/manifest.json", "companies/acme/manifest.json"} <= names
    assert [c["name"] for c in acme_customers] == [ACME_CUSTOMER]


def test_an_export_wont_write_over_one_that_is_already_there(world, tmp_path, capsys):
    out = tmp_path / "getmeds.zip"
    out.write_bytes(b"last week's backup")
    assert export.main(["--org", "getmeds", "--out", str(out)], world=world) == 1
    assert "already there" in capsys.readouterr().err
    assert out.read_bytes() == b"last week's backup"
    assert export.main(["--org", "getmeds", "--out", str(out), "--force"], world=world) == 0
    assert out.read_bytes() != b"last week's backup"


def test_an_export_of_a_company_that_isnt_there_says_so(world, tmp_path, capsys):
    assert export.main(["--org", "nobody", "--out", str(tmp_path / "x.zip")], world=world) == 1
    assert "no company 'nobody'" in capsys.readouterr().err


# --- and back in ------------------------------------------------------------------------


def test_an_export_restored_into_an_empty_company_is_the_same_world(client, as_, world, tmp_path, settings):
    letter_quote(client, as_)
    out = tmp_path / "getmeds.zip"
    assert export.main(["--org", "getmeds", "--out", str(out)], world=world) == 0
    before_rows, before_records = row_counts(world, FIRST_ORG_ID), record_counts(world, FIRST_ORG_ID)

    argv = ["restore", "--in", str(out), "--org", "getmeds-copy", "--new-ids"]
    assert export.main(argv, world=world) == 0
    copy = company_id(world, "getmeds-copy")

    assert copy != FIRST_ORG_ID
    assert row_counts(world, copy) == before_rows
    assert record_counts(world, copy) == before_records
    # The original is untouched, and the copy's letter is its own file under the reference its quote names.
    assert row_counts(world, FIRST_ORG_ID) == before_rows
    assert sorted(p.name for p in (settings.files_path / copy).iterdir()) == sorted(
        p.name for p in (settings.files_path / FIRST_ORG_ID).iterdir()
    )

    # Every link inside the copy points inside the copy: new ids all the way down, nothing left pointing home.
    records = world.records.for_org(copy)
    scopes = every_scope(world, copy)
    customers = records.find(Query("customer", scopes, limit=500))
    activities = records.find(Query("activity", scopes, limit=500))
    original = world.records.for_org(FIRST_ORG_ID).find(Query("customer", scopes, limit=500))
    assert {c["_id"] for c in customers}.isdisjoint({c["_id"] for c in original})
    assert {a["customerId"] for a in activities} <= {c["_id"] for c in customers}


def test_a_restore_into_a_database_that_lost_it_brings_the_company_back_as_itself(client, as_, world, tmp_path):
    """The reason the tool exists: the accounts database and the records are gone, and this is all there is."""
    letter_quote(client, as_)
    out = tmp_path / "getmeds.zip"
    assert export.main(["--org", "getmeds", "--out", str(out)], world=world) == 0
    before_rows, before_records = row_counts(world, FIRST_ORG_ID), record_counts(world, FIRST_ORG_ID)
    here = world.records.for_org(FIRST_ORG_ID).find(Query("customer", every_scope(world, FIRST_ORG_ID), limit=500))
    was_here = {c["_id"] for c in here}

    engine = make_engine(f"sqlite:///{(tmp_path / 'restored.db').as_posix()}")
    Base.metadata.create_all(engine)
    fresh = World(engine, Records(LocalBackend(None)), tmp_path / "restored-files")
    assert export.main(["restore", "--in", str(out), "--org", "getmeds"], world=fresh) == 0

    assert company_id(fresh, "getmeds") == FIRST_ORG_ID
    assert row_counts(fresh, FIRST_ORG_ID) == before_rows
    assert record_counts(fresh, FIRST_ORG_ID) == before_records
    back = fresh.records.for_org(FIRST_ORG_ID).find(Query("customer", every_scope(fresh, FIRST_ORG_ID), limit=500))
    assert {c["_id"] for c in back} == was_here
    assert [p.read_bytes() for p in (fresh.files_path / FIRST_ORG_ID).iterdir()] == [PDF]


def test_replace_makes_the_company_exactly_what_the_archive_says(client, as_, world, tmp_path, settings, capsys):
    """What a recovery means to the person typing it: afterwards the company is the archive, and the day's
    work that came after it is gone."""
    letter_quote(client, as_)
    out = tmp_path / "getmeds.zip"
    assert export.main(["--org", "getmeds", "--out", str(out)], world=world) == 0
    archived_rows, archived_records = row_counts(world, FIRST_ORG_ID), record_counts(world, FIRST_ORG_ID)
    archived_files = sorted(p.name for p in (settings.files_path / FIRST_ORG_ID).iterdir())

    ana, iris = as_("ana"), as_("iris")
    customer = {"team": "general", "name": "Later Lopez", "kind": "patient"}
    later = client.post("/sales/customers", json={"division": "b2c", **customer}, headers=ana)
    assert later.status_code == 201, later.text
    bought = {"code": "LATER-1", "name": "Bought later", "unit": "Box"}
    product = client.post("/inventory/products", json=bought, headers=iris)
    assert product.status_code == 201, product.text
    letter_quote(client, as_)
    assert row_counts(world, FIRST_ORG_ID) != archived_rows

    assert export.main(["restore", "--in", str(out), "--org", "getmeds", "--replace"], world=world) == 0

    assert row_counts(world, FIRST_ORG_ID) == archived_rows
    assert record_counts(world, FIRST_ORG_ID) == archived_records
    assert sorted(p.name for p in (settings.files_path / FIRST_ORG_ID).iterdir()) == archived_files
    records = world.records.for_org(FIRST_ORG_ID)
    names = {c["name"] for c in records.find(Query("customer", every_scope(world, FIRST_ORG_ID), limit=500))}
    assert "Dr. Alma Dizon" in names and "Later Lopez" not in names
    with world.engine.connect() as connection:
        assert not connection.scalar(select(func.count()).select_from(Product.__table__).where(Product.code == "LATER-1"))
    said = capsys.readouterr().out
    assert "Cleared getmeds first:" in said and "record(s)" in said


def test_replace_leaves_the_company_next_door_and_a_shared_account_alone(app, client, as_, acme, world, tmp_path):
    """Ana works for both companies. Replacing Getmeds ends her membership there and brings it back; it may
    not take her account, or anything of Acme's, with it."""
    out = tmp_path / "getmeds.zip"
    assert export.main(["--org", "getmeds", "--out", str(out)], world=world) == 0
    with app.state.sessions() as db:
        set_company(db, ACME)
        add_person(db, "ana@pharmacrm.test", "Ana Reyes", DEMO_PASSWORD, [("rep", "bnb", "bnb", "md-telesales")])
        # And someone who joined Getmeds after the archive was taken, so the archive has never heard of her.
        set_company(db, FIRST_ORG_ID)
        add_person(db, "zoe@pharmacrm.test", "Zoe Zamora", DEMO_PASSWORD, [("rep", "b2c", "b2c", "general")])
    ana = profile_id(world, "ana@pharmacrm.test")
    acme_rows, acme_records = row_counts(world, ACME), record_counts(world, ACME)

    assert export.main(["restore", "--in", str(out), "--org", "getmeds", "--replace"], world=world) == 0

    assert row_counts(world, ACME) == acme_rows
    assert record_counts(world, ACME) == acme_records
    assert profile_id(world, "olga@acme.test") is not None
    assert profile_id(world, "ana@pharmacrm.test") == ana
    assert memberships_of(world, ana) == {FIRST_ORG_ID, ACME}
    # Zoe was in no other company and is in no archive, so she is gone altogether.
    assert profile_id(world, "zoe@pharmacrm.test") is None


def test_the_recovery_path_works_on_a_freshly_migrated_database(client, as_, world, tmp_path):
    """The real thing: alembic upgrade head, then --replace. The migrations create the first company and seed
    it, so it is never an empty company and only --replace puts the archive back as it stands."""
    letter_quote(client, as_)
    out = tmp_path / "getmeds.zip"
    assert export.main(["--org", "getmeds", "--out", str(out)], world=world) == 0
    archived_rows, archived_records = row_counts(world, FIRST_ORG_ID), record_counts(world, FIRST_ORG_ID)

    url = f"sqlite:///{(tmp_path / 'recovered.db').as_posix()}"
    config = Config(str(API_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    fresh = World(make_engine(url), Records(LocalBackend(None)), tmp_path / "recovered-files")
    with fresh.engine.connect() as connection:
        assert export.company_row_count(connection, FIRST_ORG_ID) > 0

    assert export.main(["restore", "--in", str(out), "--org", "getmeds", "--replace"], world=fresh) == 0

    assert row_counts(fresh, FIRST_ORG_ID) == archived_rows
    assert record_counts(fresh, FIRST_ORG_ID) == archived_records
    assert [p.read_bytes() for p in (fresh.files_path / FIRST_ORG_ID).iterdir()] == [PDF]


def test_a_restore_of_a_company_with_rows_in_it_waits_to_be_told_twice(client, world, tmp_path, capsys):
    """A company that already holds something is a mistake waiting to happen, so --force has to say so."""
    out = tmp_path / "getmeds.zip"
    assert export.main(["--org", "getmeds", "--out", str(out)], world=world) == 0
    with world.engine.begin() as connection:
        connection.execute(
            Organization.__table__.insert().values(id=SPARE, slug="spare", name="Spare Room", brand_name="Spare")
        )
        connection.execute(
            ApiKey.__table__.insert().values(org_id=SPARE, id="k1", name="a key that was here first", secret_hash="x")
        )

    argv = ["restore", "--in", str(out), "--org", "spare"]
    assert export.main(argv, world=world) == 1
    # What a recovery wants is named first; --force is for filling a company a piece at a time.
    said = capsys.readouterr().err
    assert "already holds" in said and said.index("--replace") < said.index("--force")
    assert row_counts(world, SPARE) == {**{t.name: 0 for t in company_tables()}, "api_keys": 1}

    assert export.main([*argv, "--force", "--new-ids"], world=world) == 0
    assert row_counts(world, SPARE) == {**row_counts(world, FIRST_ORG_ID), "api_keys": 1}


def test_a_restore_next_to_the_company_it_came_from_stops_rather_than_muddle_them(client, world, tmp_path, capsys):
    """Without --new-ids a restore keeps every id, so loading it beside its source can only clash. It says so
    and leaves both alone."""
    out = tmp_path / "getmeds.zip"
    assert export.main(["--org", "getmeds", "--out", str(out)], world=world) == 0
    before = row_counts(world, FIRST_ORG_ID)

    assert export.main(["restore", "--in", str(out), "--org", "getmeds-copy"], world=world) == 1
    assert "--new-ids" in capsys.readouterr().err
    assert company_id(world, "getmeds-copy") is None
    assert row_counts(world, FIRST_ORG_ID) == before


def test_a_restore_of_a_file_that_isnt_an_export_says_so(world, tmp_path, capsys):
    broken = tmp_path / "broken.zip"
    with ZipFile(broken, "w") as archive:
        archive.writestr("hello.txt", "not an export")
    assert export.main(["restore", "--in", str(broken), "--org", "getmeds-copy"], world=world) == 1
    assert "doesn't look like an Orbit export" in capsys.readouterr().err
    assert company_id(world, "getmeds-copy") is None


# --- the dated archives -----------------------------------------------------------------


def nightly(out_dir: Path, first: datetime, days: int) -> list[Path]:
    """A run of nightly archives, newest first, with nothing to read inside them: retention goes by the name."""
    made = []
    for day in range(days):
        path = out_dir / backup.archive_name(first - timedelta(days=day))
        path.write_bytes(b"")
        made.append(path)
    return made


def test_a_backup_keeps_the_last_month_and_a_year_of_month_firsts(tmp_path, capsys):
    out_dir = tmp_path / "backups"
    out_dir.mkdir()
    latest = datetime(2026, 9, 21, 3, 0, 0)
    nightly(out_dir, latest, 500)  # back to May 2025

    gone = backup.sweep(backup.dated_archives(out_dir), 30, 12, dry_run=False)
    left = {path.name for _, path in backup.dated_archives(out_dir)}

    # The last 30 nights, whole.
    assert {backup.archive_name(latest - timedelta(days=d)) for d in range(30)} <= left
    # The first archive of each of the last 12 months, September back to last October.
    firsts = {backup.archive_name(datetime(year, month, 1, 3, 0, 0))
              for year, month in [(2026, m) for m in range(1, 10)] + [(2025, m) for m in (10, 11, 12)]}
    assert firsts <= left
    # Nothing else: no older month-firsts, and no ordinary night older than 30 days.
    assert left == firsts | {backup.archive_name(latest - timedelta(days=d)) for d in range(30)}
    assert backup.archive_name(datetime(2025, 9, 1, 3, 0, 0)) in {p.name for p in gone}
    assert backup.archive_name(datetime(2026, 7, 15, 3, 0, 0)) in {p.name for p in gone}
    assert len(gone) == 500 - len(left)
    assert capsys.readouterr().out.count("deleted ") == len(gone)


def test_a_dry_run_deletes_nothing(tmp_path, capsys):
    out_dir = tmp_path / "backups"
    out_dir.mkdir()
    made = nightly(out_dir, datetime(2026, 9, 21, 3, 0, 0), 40)
    gone = backup.sweep(backup.dated_archives(out_dir), 30, 12, dry_run=True)
    # The newest 30, and the oldest of the lot, which is as far back as August goes here.
    assert [p.name for p in gone] == [p.name for p in made[30:-1]]
    assert all(p.exists() for p in made)
    assert capsys.readouterr().out.count("would delete ") == len(gone)


def test_keep_daily_and_keep_monthly_are_the_tools_to_turn(tmp_path):
    out_dir = tmp_path / "backups"
    out_dir.mkdir()
    nightly(out_dir, datetime(2026, 9, 21, 3, 0, 0), 120)
    backup.sweep(backup.dated_archives(out_dir), 3, 2, dry_run=False)
    assert {p.name for _, p in backup.dated_archives(out_dir)} == {
        backup.archive_name(datetime(2026, 9, 21, 3, 0, 0) - timedelta(days=d)) for d in range(3)
    } | {backup.archive_name(datetime(2026, m, 1, 3, 0, 0)) for m in (8, 9)}


def test_a_backup_writes_one_archive_of_every_company_and_reads_it_back(client, acme, world, tmp_path, capsys):
    out_dir = tmp_path / "backups"
    assert backup.main(["--out-dir", str(out_dir)], world=world) == 0
    archives = backup.dated_archives(out_dir)
    assert len(archives) == 1
    assert backup.verify(archives[0][1])["companies"] == ["acme", "getmeds"]
    out = capsys.readouterr().out
    assert "getmeds" in out and "1 archive(s) kept, 0 deleted." in out


def test_a_backup_that_cant_be_read_back_is_a_failure(tmp_path, capsys):
    out_dir = tmp_path / "backups"
    out_dir.mkdir()
    damaged = out_dir / backup.archive_name(datetime(2026, 9, 21, 3, 0, 0))
    damaged.write_bytes(b"not a zip at all")
    with pytest.raises(export.ExportError, match="can't be read back"):
        backup.verify(damaged)

    with ZipFile(damaged, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"formatVersion": 1, "companies": []}))
    with pytest.raises(export.ExportError, match="names no companies"):
        backup.verify(damaged)
