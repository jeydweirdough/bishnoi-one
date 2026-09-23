# Backups

A backup nobody has restored is a rumour. This page is the whole routine: what
runs, where it goes, and how you prove it works.

## What one archive holds

`app/tools/backup.py` writes a single dated zip holding **every company**:

- every table, one JSON line per row, in an order that can be loaded back;
- the records (customers, activities, follow-ups, quotes);
- the uploaded files, byte for byte;
- a manifest with the row counts and the database revision it was taken at.

Two tables are left out on purpose and named in the manifest: `sessions` and
`sso_codes`. They are sign-in state that expires in hours, and restoring them
would only put stale tokens back.

## Running it by hand

```
cd orbit-core/backend
uv run python -m app.tools.backup --out-dir D:\orbit-backups
```

It prints one line per archive it writes or deletes, checks the archive opens
before it deletes anything, and exits non-zero if it could not. Add `--dry-run`
to see what it would do.

By default it keeps the last 30 daily archives and the first archive of each of
the last 12 months. `--keep-daily` and `--keep-monthly` change that.

## Running it every night

`scripts\backup-daily.ps1` is the wrapper Windows Task Scheduler calls. Set the
folder at the top of it, then register the task **as an administrator**:

```
schtasks /Create /TN "Orbit backup" /TR "powershell -ExecutionPolicy Bypass -File C:\Users\Getmeds Backend\Desktop\orbit\orbit-core\backend\scripts\backup-daily.ps1" /SC DAILY /ST 02:00 /RL HIGHEST /F
```

Check it afterwards with `schtasks /Query /TN "Orbit backup" /V /FO LIST`, and
read `backup.log` in the backup folder the next morning.

The script writes that log and exits non-zero on failure, so Task Scheduler's
"Last Run Result" is meaningful. Set the task to **notify you on failure** — a
backup that quietly stops is the usual way people lose data.

## The second copy

The archive is on the same machine as the database until you move it. One copy
somewhere else is what survives a fire, a theft or a ransomware run. Point the
folder at a synced drive, or add a copy step to the script.

An archive holds customer names and staff details. Treat it like the database:
somewhere private, and never in a shared folder or a chat.

## Restoring

Into a database that already has the company:

```
uv run python -m app.tools.export restore --in orbit-20260921-020000.zip --org getmeds --replace
```

`--replace` clears what that company currently holds and puts the archive in its
place. Without it the tool refuses rather than merging two versions of a company
together.

To load a copy of a company **beside** the real one, to look at without touching
anything live:

```
uv run python -m app.tools.export restore --in orbit-20260921-020000.zip --org getmeds-copy --new-ids
```

## Proving it works — every quarter

Put it in the calendar. It takes fifteen minutes.

1. Take the newest archive.
2. Make an empty database: point `DATABASE_URL`, `LOCAL_STORE_PATH` and
   `FILES_PATH` at a scratch folder, then `uv run alembic upgrade head`.
3. Restore into it with `--replace`.
4. Run the app against that database and sign in.
5. Check a handful of things by eye: a customer's history, a quote's total, a
   guarantee letter that opens, the number of people in Settings.

If any step fails, the backup is not a backup yet. Fix it the same week.
