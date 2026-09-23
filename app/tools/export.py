"""One company's whole world in a zip, and the way back in.

    uv run python -m app.tools.export --org getmeds --out getmeds.zip
    uv run python -m app.tools.export --all-companies --out everything.zip
    uv run python -m app.tools.export restore --in getmeds.zip --org getmeds-copy

Inside a one-company zip:

    manifest.json           the company, when it was taken, how many of everything, and the migration it was at
    tables/<table>.jsonl    one JSON object per database row; dates as ISO text, bytes as base64
    records/<type>.jsonl    customers, activities, follow-ups and quotes from the records store
    files/<reference>       the uploaded guarantee letters, under the reference their records name

--all-companies puts every company under companies/<slug>/ in that same shape,
with a short manifest.json at the top naming them.

Putting one back, after losing a database:

    uv run alembic upgrade head
    uv run python -m app.tools.export restore --in getmeds.zip --org getmeds --replace

--replace empties the company first -- its rows, its records and its uploaded
files -- so that afterwards it is exactly what the archive says and nothing
else. It is the one to reach for in a recovery: the migrations create the
first company and seed it (its lists, its roles, its order settings), so a
database that has only been migrated is never an empty company, and loading an
archive into it any other way would pile the archive on top of that seeding.

Without --replace a restore adds to what is already there and refuses a
company that holds rows; --force goes on anyway, which is only right for a
company being filled a piece at a time. --new-ids gives every row and record a
new id and rewrites whatever pointed at the old one: that is how a company is
loaded alongside the one it came from (a copy to try something on) instead of
over it.

People are shared between companies, so --replace ends their membership here
and only takes an account away when this was the last company it belonged to.

Sign-in sessions and their one-time codes are never exported. They last hours,
they are not the company's work, and nobody should be signed in again by a
restore -- but --replace does clear them, so a replaced company signs its
people in afresh.
"""

import argparse
import base64
import json
import os
import secrets
import shutil
import sys
import uuid
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    Date,
    DateTime,
    Engine,
    LargeBinary,
    MetaData,
    String,
    Table,
    func,
    inspect,
    or_,
    select,
)
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.db import make_engine
from app.models import SHARED_TABLES, Base, Organization, Subdivision
from app.routers.sales import CHILD_TYPES, CUSTOMER
from app.scope import Scope
from app.store import build_records
from app.store.files import REF
from app.store.query import Query
from app.store.records import Create, Delete, Records, StoreError
from app.tenancy import ORG_KEY

FORMAT_VERSION = 1
RECORD_TYPES = (CUSTOMER, *CHILD_TYPES)
# Rows and records are read, written and inserted a batch at a time, so a big
# company's export costs the same memory as a small one's.
BATCH = 500
# SQLite takes 999 bound values in one statement, so lists of ids go in pieces.
ID_BATCH = 400

# Sign-in state, and it points at sso_clients, which belong to the platform rather than to any company.
SKIPPED_TABLES = frozenset({"sessions", "sso_codes"})
# Shared tables a company keeps a share of: its people, and what belongs to a person.
PEOPLE_TABLES = ("profiles", "local_credentials", "profile_photos")


class ExportError(RuntimeError):
    """Something a person running the tool needs to read and act on."""


@dataclass(frozen=True)
class World:
    """The three places a company's data lives: its rows, its records, its files."""

    engine: Engine
    records: Records
    files_path: Path | None


def open_world(settings: Settings) -> World:
    return World(make_engine(settings.database_url), build_records(settings), settings.files_path)


def table(name: str) -> Table:
    return Base.metadata.tables[name]


def all_company_tables() -> list[Table]:
    """Every table that carries a company, in an order that never inserts a child before its parent."""
    return [t for t in Base.metadata.sorted_tables if t.name not in SHARED_TABLES]


def company_tables() -> list[Table]:
    """The ones an archive carries: everything of the company's except the sign-in state."""
    return [t for t in all_company_tables() if t.name not in SKIPPED_TABLES]


# --- rows in and out of JSON ------------------------------------------------------------


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value


def from_json(column_type: Any, value: Any) -> Any:
    """The other way. SQLite hands back plain text and 0/1, so the column says what it meant."""
    if value is None:
        return None
    if isinstance(column_type, LargeBinary):
        return base64.b64decode(value)
    if isinstance(column_type, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(column_type, Date):
        return date.fromisoformat(value)
    if isinstance(column_type, Boolean):
        return bool(value)
    return value


def row_to_json(row: dict) -> dict:
    return {key: json_ready(value) for key, value in row.items()}


def row_from_json(target: Table, row: dict) -> dict:
    return {key: from_json(target.c[key].type, value) for key, value in row.items() if key in target.c}


# --- reading a company ------------------------------------------------------------------


def find_company(connection: Connection, key: str) -> dict:
    orgs = Organization.__table__
    found = connection.execute(select(orgs).where(or_(orgs.c.slug == key, orgs.c.id == key))).mappings().first()
    if found is None:
        raise ExportError(f"There is no company {key!r}. Give its short name, like getmeds, or its id.")
    return dict(found)


def every_company(connection: Connection) -> list[dict]:
    orgs = Organization.__table__
    return [dict(r) for r in connection.execute(select(orgs).order_by(orgs.c.slug)).mappings()]


# Alembic's own bookkeeping table, which isn't one of the models.
ALEMBIC_VERSION = Table("alembic_version", MetaData(), Column("version_num", String(32)))


def alembic_revision(connection: Connection) -> str | None:
    """None when the database was built straight from the models (tests) instead of by migrations."""
    if not inspect(connection).has_table(ALEMBIC_VERSION.name):
        return None
    return connection.scalar(select(ALEMBIC_VERSION.c.version_num))


def company_rows(connection: Connection, source: Table, org_id: str) -> Iterator[dict]:
    statement = select(source).where(source.c[ORG_KEY] == org_id).order_by(*source.primary_key.columns)
    result = connection.execute(statement.execution_options(yield_per=BATCH))
    for row in result.mappings():
        yield dict(row)


def rows_by_ids(connection: Connection, source: Table, column: str, ids: Sequence[str]) -> Iterator[dict]:
    for start in range(0, len(ids), ID_BATCH):
        chunk = ids[start : start + ID_BATCH]
        statement = select(source).where(source.c[column].in_(chunk)).order_by(source.c[column])
        for row in connection.execute(statement).mappings():
            yield dict(row)


def company_people(connection: Connection, org_id: str) -> list[str]:
    """Its members, and anyone else its rows still point at, or a restore would leave dangling links.

    There are as many of these as the company has staff, so holding the ids is nothing like holding the rows.
    """
    memberships = table("memberships")
    people = set(connection.scalars(select(memberships.c.user_id).where(memberships.c[ORG_KEY] == org_id)))
    for name, column in (("audit_log", "actor_id"), ("api_keys", "created_by_id")):
        linked = table(name)
        people |= {
            person
            for person in connection.scalars(select(linked.c[column]).where(linked.c[ORG_KEY] == org_id))
            if person
        }
    return sorted(people)


def company_scopes(connection: Connection, org_id: str) -> frozenset[Scope]:
    """The teams whose records to read. A record in a team that no longer exists is invisible to the app
    too, which is why teams are switched off rather than deleted (app/models.py)."""
    teams = Subdivision.__table__
    rows = connection.execute(select(teams.c.division_code, teams.c.code).where(teams.c[ORG_KEY] == org_id))
    return frozenset(Scope(division, team) for division, team in rows)


def store_records(records: Records, doc_type: str, scopes: frozenset[Scope]) -> Iterator[dict]:
    """A page at a time, oldest id first, so a big company's records never sit in memory at once."""
    total = records.count(Query(doc_type, scopes))
    offset = 0
    while offset < total:
        page = Query(doc_type, scopes, order=(("_id", "asc"),), offset=offset, limit=BATCH)
        yield from records.find(page)
        offset += BATCH


def company_files(files_path: Path | None, org_id: str) -> list[Path]:
    if files_path is None:
        return []
    folder = files_path / org_id
    return sorted(p for p in folder.iterdir() if p.is_file() and REF.fullmatch(p.name)) if folder.is_dir() else []


# --- writing the zip --------------------------------------------------------------------


def write_jsonl(archive: ZipFile, name: str, rows: Iterable[dict]) -> int:
    written = 0
    with archive.open(name, "w") as out:
        for row in rows:
            out.write((json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
            written += 1
    return written


def write_file(archive: ZipFile, name: str, path: Path) -> None:
    with path.open("rb") as source, archive.open(name, "w") as out:
        shutil.copyfileobj(source, out, BATCH * 1024)


def write_manifest(archive: ZipFile, name: str, manifest: dict) -> None:
    archive.writestr(name, json.dumps(manifest, indent=1, ensure_ascii=False))


def export_company(archive: ZipFile, prefix: str, world: World, connection: Connection, org: dict) -> dict:
    """Writes one company's folder and returns its manifest. Counts come from what was written, not from a
    count taken beforehand, so the manifest always describes the zip."""
    org_id = org["id"]
    counts: dict[str, int] = {}
    people = company_people(connection, org_id)

    counts["organizations"] = write_jsonl(archive, f"{prefix}tables/organizations.jsonl", [row_to_json(org)])
    for name in PEOPLE_TABLES:
        shared = table(name)
        column = "id" if name == "profiles" else "user_id"
        rows = (row_to_json(row) for row in rows_by_ids(connection, shared, column, people))
        counts[name] = write_jsonl(archive, f"{prefix}tables/{name}.jsonl", rows)
    for source in company_tables():
        rows = (row_to_json(row) for row in company_rows(connection, source, org_id))
        counts[source.name] = write_jsonl(archive, f"{prefix}tables/{source.name}.jsonl", rows)

    scopes = company_scopes(connection, org_id)
    records = world.records.for_org(org_id)
    kept: dict[str, int] = {}
    for doc_type in RECORD_TYPES:
        kept[doc_type] = write_jsonl(
            archive, f"{prefix}records/{doc_type}.jsonl", store_records(records, doc_type, scopes)
        )

    files = company_files(world.files_path, org_id)
    for path in files:
        write_file(archive, f"{prefix}files/{path.name}", path)

    manifest = {
        "formatVersion": FORMAT_VERSION,
        "takenAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "alembicRevision": alembic_revision(connection),
        "company": {"id": org_id, "slug": org["slug"], "name": org["name"]},
        "tables": counts,
        "records": kept,
        "files": len(files),
        "skippedTables": sorted(SKIPPED_TABLES),
    }
    write_manifest(archive, f"{prefix}manifest.json", manifest)
    return manifest


def export(world: World, out: Path, *, org: str | None, all_companies: bool, force: bool) -> list[dict]:
    if out.exists() and not force:
        raise ExportError(f"{out} is already there. Pick another name, or pass --force to write over it.")
    out.parent.mkdir(parents=True, exist_ok=True)
    manifests: list[dict] = []
    # Written beside the name it was asked for and moved into place at the end, the way the record store saves
    # (app/store/local.py), so a run that stops half way never leaves something that looks like a backup.
    partial = out.with_name(out.name + ".part")
    try:
        with world.engine.connect() as connection, ZipFile(partial, "w", ZIP_DEFLATED) as archive:
            companies = every_company(connection) if all_companies else [find_company(connection, org or "")]
            if not companies:
                raise ExportError("There are no companies in this database yet.")
            for company in companies:
                prefix = f"companies/{company['slug']}/" if all_companies else ""
                manifests.append(export_company(archive, prefix, world, connection, company))
            if all_companies:
                write_manifest(
                    archive,
                    "manifest.json",
                    {
                        "formatVersion": FORMAT_VERSION,
                        "takenAt": manifests[0]["takenAt"],
                        "alembicRevision": manifests[0]["alembicRevision"],
                        "companies": [m["company"]["slug"] for m in manifests],
                    },
                )
        os.replace(partial, out)
    finally:
        partial.unlink(missing_ok=True)
    return manifests


def print_export(out: Path, manifests: list[dict]) -> None:
    for manifest in manifests:
        company = manifest["company"]
        print(f"\n{company['slug']} ({company['name']})")
        lines = [(name, count) for name, count in manifest["tables"].items() if count]
        lines += [(f"records/{name}", count) for name, count in manifest["records"].items() if count]
        lines += [("files", manifest["files"])]
        for name, count in lines:
            print(f"  {name:<28}{count:>8}")
        print(f"  {'':<28}{'':->8}")
        print(f"  {'in all':<28}{sum(count for _, count in lines):>8}")
    print(f"\nWritten to {out} ({out.stat().st_size:,} bytes).")


# --- reading the zip back ---------------------------------------------------------------


def read_manifest(archive: ZipFile, name: str) -> dict:
    try:
        manifest = json.loads(archive.read(name))
    except KeyError as exc:
        raise ExportError(f"{name} is missing; this doesn't look like an Orbit export.") from exc
    except ValueError as exc:
        raise ExportError(f"{name} isn't readable; the export may be damaged.") from exc
    if manifest.get("formatVersion") != FORMAT_VERSION:
        raise ExportError(f"This export is format {manifest.get('formatVersion')}; this tool reads {FORMAT_VERSION}.")
    return manifest


def company_prefix(archive: ZipFile, wanted: str | None) -> tuple[str, dict]:
    """Where the company sits in the zip: the top of a one-company export, or companies/<slug>/."""
    top = read_manifest(archive, "manifest.json")
    if "company" in top:
        if wanted and wanted != top["company"]["slug"]:
            raise ExportError(f"This export holds {top['company']['slug']}, not {wanted}.")
        return "", top
    inside = top.get("companies") or []
    if wanted is None and len(inside) != 1:
        raise ExportError(f"This export holds {len(inside)} companies ({', '.join(inside)}). Pick one with --from.")
    slug = wanted or inside[0]
    if slug not in inside:
        raise ExportError(f"This export doesn't hold {slug}. It holds: {', '.join(inside)}.")
    return f"companies/{slug}/", read_manifest(archive, f"companies/{slug}/manifest.json")


def read_jsonl(archive: ZipFile, name: str) -> Iterator[dict]:
    """Nothing in the zip is held in memory: each line is parsed and handed on."""
    if name not in archive.namelist():
        return
    with archive.open(name) as lines:
        for line in lines:
            if line.strip():
                yield json.loads(line)


def fresh_id(old: str) -> str:
    """A new id shaped like the old one, so it still fits the column it goes in."""
    if len(old) == 36 and old.count("-") == 4:
        return str(uuid.uuid4())
    return secrets.token_hex(32)[: len(old)] or str(uuid.uuid4())


def new_id_map(archive: ZipFile, prefix: str) -> dict[str, str]:
    """Old id -> new id for everything with an id of its own: rows keyed by `id` alone, and every record.

    Only ids are held, never the rows they came from, and every one is a uuid or a long random string, so
    rewriting a value that matches one is safe.
    """
    mapping: dict[str, str] = {}
    for source in company_tables():
        if [c.name for c in source.primary_key.columns] != ["id"]:
            continue
        for row in read_jsonl(archive, f"{prefix}tables/{source.name}.jsonl"):
            mapping[row["id"]] = fresh_id(row["id"])
    for doc_type in RECORD_TYPES:
        for doc in read_jsonl(archive, f"{prefix}records/{doc_type}.jsonl"):
            mapping[doc["_id"]] = fresh_id(doc["_id"])
    return mapping


def with_new_ids(value: Any, mapping: dict[str, str]) -> Any:
    """Every id in a row or a record, however deeply nested, swapped for its new one."""
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [with_new_ids(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: with_new_ids(item, mapping) for key, item in value.items()}
    return value


# --- restoring --------------------------------------------------------------------------


def company_row_count(connection: Connection, org_id: str) -> int:
    return sum(
        connection.scalar(select(func.count()).select_from(t).where(t.c[ORG_KEY] == org_id)) or 0
        for t in all_company_tables()
    )


def clear_rows(connection: Connection, org_id: str) -> int:
    """Children before parents, and every statement names the company, so no other company's row is in reach.

    A member's manager is a link within the same table, so those are let go of first rather than relying on
    the order rows happen to be deleted in."""
    removed = 0
    for target in reversed(all_company_tables()):
        deferred = self_referring_columns(target)
        if deferred:
            connection.execute(target.update().where(target.c[ORG_KEY] == org_id).values(dict.fromkeys(deferred)))
        removed += connection.execute(target.delete().where(target.c[ORG_KEY] == org_id)).rowcount
    return removed


def clear_records(records: Records, scopes: frozenset[Scope]) -> int:
    """The store checks every id against the company before it deletes any of them (app/store/records.py)."""
    removed = 0
    for doc_type in RECORD_TYPES:
        ids = [doc["_id"] for doc in store_records(records, doc_type, scopes)]
        for start in range(0, len(ids), BATCH):
            batch = ids[start : start + BATCH]
            records.commit([Delete(doc_id) for doc_id in batch])
            removed += len(batch)
    return removed


def clear_files(files_path: Path | None, org_id: str) -> int:
    gone = company_files(files_path, org_id)
    for path in gone:
        path.unlink()
    return len(gone)


def forget_people(connection: Connection, people: Sequence[str]) -> int:
    """A person belongs to the platform, not to one company, so an account only goes when this was the last
    company it was in and nothing of anyone else's still names it: an audit line, an API key, platform admin.
    Their password and picture go with them (the accounts database cascades)."""
    profiles, memberships = table("profiles"), table("memberships")
    still_named = (("audit_log", "actor_id"), ("api_keys", "created_by_id"), ("platform_admins", "user_id"))
    gone = 0
    for user_id in people:
        elsewhere = connection.scalar(
            select(func.count()).select_from(memberships).where(memberships.c.user_id == user_id)
        )
        named = any(
            connection.scalar(select(func.count()).select_from(table(name)).where(table(name).c[column] == user_id))
            for name, column in still_named
        )
        if elsewhere or named:
            continue
        connection.execute(profiles.delete().where(profiles.c.id == user_id))
        gone += 1
    return gone


def clear_company(connection: Connection, world: World, org_id: str) -> dict[str, int]:
    """Everything the company holds, in all three places it holds it, so that what is loaded next is all it has.

    Read what is needed before deleting anything: the teams say which records are the company's, and the
    members say whose accounts to look at once their memberships are gone."""
    people = company_people(connection, org_id)
    scopes = company_scopes(connection, org_id)
    records = clear_records(world.records.for_org(org_id), scopes)
    files = clear_files(world.files_path, org_id)
    rows = clear_rows(connection, org_id)
    accounts = forget_people(connection, people)  # once their memberships have gone, or they all look busy
    return {"rows": rows, "records": records, "files": files, "people": accounts}


def target_company(connection: Connection, slug: str, exported: dict, *, force: bool, replace: bool) -> dict:
    """The company being restored into: the one with this short name, or a new one shaped like the old one.

    Under its own short name into a database that has lost it, a company comes back as itself, id and all,
    which is what anything outside Orbit holding its id needs. Under any other name it is a new company.
    """
    orgs = Organization.__table__
    found = connection.execute(select(orgs).where(orgs.c.slug == slug)).mappings().first()
    if found is None:
        org_id = exported["id"] if slug == exported["slug"] else str(uuid.uuid4())
        row = row_from_json(orgs, {**exported, "id": org_id, "slug": slug})
        connection.execute(orgs.insert().values(row))
        return row
    if replace:
        # The archive says what the company is, down to its name, its currency and how it numbers orders.
        row = row_from_json(orgs, {**exported, "id": found["id"], "slug": slug})
        connection.execute(orgs.update().where(orgs.c.id == found["id"]).values(row))
        return row
    rows = company_row_count(connection, found["id"])
    if rows and not force:
        raise ExportError(
            f"{slug} already holds {rows} row{'' if rows == 1 else 's'}, as a company does once the migrations "
            "have seeded it. To put this archive back as it stands, --replace clears the company first; "
            "--force adds the archive on top of whatever is there."
        )
    return dict(found)


def self_referring_columns(target: Table) -> list[str]:
    """Columns pointing at the same table (a member's manager). They wait until the rows they point at are in."""
    return [
        column
        for constraint in target.foreign_key_constraints
        if constraint.referred_table is target
        for column in constraint.column_keys
        if column != ORG_KEY
    ]


def insert_rows(connection: Connection, target: Table, rows: Iterable[dict], org_id: str, mapping: dict[str, str]) -> int:
    deferred = self_referring_columns(target)
    keys = [c.name for c in target.primary_key.columns]
    batch: list[dict] = []
    later: list[dict] = []
    written = 0

    def flush() -> None:
        nonlocal written
        if batch:
            connection.execute(target.insert(), batch)
            written += len(batch)
            batch.clear()

    for row in rows:
        row = row_from_json(target, {**with_new_ids(row, mapping), ORG_KEY: org_id})
        if any(row.get(column) is not None for column in deferred):
            later.append(row)
            row = {**row, **dict.fromkeys(deferred)}
        batch.append(row)
        if len(batch) >= BATCH:
            flush()
    flush()
    for row in later:
        where = [target.c[key] == row[key] for key in keys]
        connection.execute(target.update().where(*where).values({column: row[column] for column in deferred}))
    return written


def insert_missing(connection: Connection, target: Table, rows: Iterable[dict], unique: Sequence[str]) -> int:
    """People are shared, so a restore only adds the ones this database has never seen (by id, and by email)."""
    written = 0
    for row in rows:
        row = row_from_json(target, row)
        here = [target.c[column] == row[column] for column in unique if row.get(column) is not None]
        if connection.scalar(select(func.count()).select_from(target).where(or_(*here))):
            continue
        connection.execute(target.insert().values(row))
        written += 1
    return written


def restore_records(archive: ZipFile, prefix: str, records: Records, mapping: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for doc_type in RECORD_TYPES:
        batch: list[Create] = []
        counts[doc_type] = 0
        for doc in read_jsonl(archive, f"{prefix}records/{doc_type}.jsonl"):
            # The store gives a record its own company stamp, revision and times; only what was typed comes back.
            doc = {k: v for k, v in with_new_ids(doc, mapping).items() if k in ("_id", "_type") or not k.startswith("_")}
            batch.append(Create({k: v for k, v in doc.items() if k != "orgId"}))
            if len(batch) >= BATCH:
                records.commit(batch)
                counts[doc_type] += len(batch)
                batch = []
        records.commit(batch)
        counts[doc_type] += len(batch)
    return counts


def restore_files(archive: ZipFile, prefix: str, files_path: Path | None, org_id: str) -> int:
    """Straight into the company's folder under the reference it had: FileStore hands out a new reference for
    every file it is given, and a restored quote has to find its letter again."""
    names = [n for n in archive.namelist() if n.startswith(f"{prefix}files/") and REF.fullmatch(n.rsplit("/", 1)[-1])]
    if not names or files_path is None:
        return 0
    folder = files_path / org_id
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        with archive.open(name) as source, (folder / name.rsplit("/", 1)[-1]).open("wb") as out:
            shutil.copyfileobj(source, out, BATCH * 1024)
    return len(names)


def restore(
    world: World, source: Path, slug: str, *, from_company: str | None, force: bool, new_ids: bool, replace: bool
) -> dict:
    if not source.is_file():
        raise ExportError(f"There is no export at {source}.")
    with ZipFile(source) as archive, world.engine.begin() as connection:
        prefix, manifest = company_prefix(archive, from_company)
        exported = next(read_jsonl(archive, f"{prefix}tables/organizations.jsonl"), None)
        if exported is None:
            raise ExportError("This export has no company row; it may be damaged.")
        company = target_company(connection, slug, exported, force=force, replace=replace)
        removed = clear_company(connection, world, company["id"]) if replace else None
        mapping = new_id_map(archive, prefix) if new_ids else {}

        counts: dict[str, int] = {}
        for name in PEOPLE_TABLES:
            shared = table(name)
            unique = ["id", "email"] if name == "profiles" else ["user_id"]
            counts[name] = insert_missing(connection, shared, read_jsonl(archive, f"{prefix}tables/{name}.jsonl"), unique)
        for target in company_tables():
            rows = read_jsonl(archive, f"{prefix}tables/{target.name}.jsonl")
            counts[target.name] = insert_rows(connection, target, rows, company["id"], mapping)
        kept = restore_records(archive, prefix, world.records.for_org(company["id"]), mapping)
        files = restore_files(archive, prefix, world.files_path, company["id"])

    return {
        "company": {"id": company["id"], "slug": slug, "name": company["name"]},
        "from": manifest["company"],
        "removed": removed,
        "tables": counts,
        "records": kept,
        "files": files,
    }


def print_restore(done: dict) -> None:
    company, came_from, removed = done["company"], done["from"], done["removed"]
    if removed:
        people = f", and {removed['people']} account(s) that were in no other company" if removed["people"] else ""
        print(
            f"Cleared {company['slug']} first: {removed['rows']} row(s), {removed['records']} record(s), "
            f"{removed['files']} file(s){people}."
        )
    print(f"{came_from['slug']} ({came_from['name']}) restored into {company['slug']}, company {company['id']}.")
    for name, count in done["tables"].items():
        if count:
            print(f"  {name:<28}{count:>8}")
    for name, count in done["records"].items():
        if count:
            print(f"  {f'records/{name}':<28}{count:>8}")
    print(f"  {'files':<28}{done['files']:>8}")


# --- the command line -------------------------------------------------------------------

EXPORT_TROUBLE = "The database or the records store wouldn't give up everything, so the zip is not a whole export:"
# An export carries the ids it was taken with, so the usual reason a restore stops is data that is here already.
RESTORE_TROUBLE = (
    "The restore stopped part-way. The database rows are back as they were, but any records and files it had "
    "already written are not, so run it again with --replace, which clears the company before loading. If this "
    "is a copy of a company that is still here, --new-ids gives everything new ids and loads it alongside.\n"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.tools.export", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command")
    back = sub.add_parser("restore", help="load an export back into a company")
    back.add_argument("--in", dest="source", metavar="FILE", required=True, help="the export to read")
    back.add_argument("--org", required=True, help="the short name of the company to restore into")
    back.add_argument("--from", dest="from_company", metavar="SLUG", help="which company, in an --all-companies export")
    mode = back.add_mutually_exclusive_group()
    mode.add_argument("--replace", action="store_true", help="clear the company first, so it becomes this archive")
    mode.add_argument("--force", action="store_true", help="add the archive on top of what the company has")
    back.add_argument("--new-ids", action="store_true", help="give every row and record a new id (a copy to work on)")
    parser.add_argument("--org", help="the company's short name (slug) or id")
    parser.add_argument("--all-companies", action="store_true", help="every company, each under companies/<slug>/")
    parser.add_argument("--out", metavar="FILE", help="the zip to write")
    parser.add_argument("--force", action="store_true", help="write over --out if it is already there")
    return parser


def main(argv: list[str] | None = None, world: World | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "restore" and not (args.out and (args.org or args.all_companies)):
        parser.error("say what to write with --out, and which company with --org or --all-companies")
    if args.command != "restore" and args.org and args.all_companies:
        parser.error("--org is for one company; --all-companies is for every company")

    try:
        world = world or open_world(get_settings())
        if args.command == "restore":
            done = restore(
                world,
                Path(args.source),
                args.org,
                from_company=args.from_company,
                force=args.force,
                new_ids=args.new_ids,
                replace=args.replace,
            )
            print_restore(done)
        else:
            out = Path(args.out)
            print_export(out, export(world, out, org=args.org, all_companies=args.all_companies, force=args.force))
    except ExportError as exc:
        print(exc, file=sys.stderr)
        return 1
    except (StoreError, SQLAlchemyError) as exc:
        print(f"{RESTORE_TROUBLE if args.command == 'restore' else EXPORT_TROUBLE}\n  {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Couldn't read or write that file: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
