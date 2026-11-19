# Bishnoi One Inventory — API

Inventory's own backend: what you have, where it is, how much, what is
moving, and what needs attention. It is a module of the one backend (`backend/main.py`), under `/inventory`; its screens are in the one app
(`bishnoi-one-app/frontend`, at `/inventory`).

It has **its own sign-in**. Accounts live in this app's own database, and an
account here signs in to this app only.

## Running it

```
cd backend               # the one backend; settings in backend/.env (see backend/.env.example)
uv sync
uv run python -m modules.inventory.tools.users add --email you@example.com --name "Your Name"   # an Administrator
uv run main.py            # every module; this one at http://127.0.0.1:8300/inventory  (docs at /inventory/docs)
uv run python -m pytest modules/inventory/tests
```

The database is brought up to date on every start (`migrate.py`): SQLite
in `.data/` unless `DATABASE_URL` says otherwise. Every table is `nbin_…`
(Bishnoi One INventory), and so is the migration table, `nbin_alembic_version`. A
database from before migrations (plain `users` and `sessions`) is carried
over: its admins become Administrators, the rest Warehouse.

For something to try: `uv run python -m modules.inventory.tools.users demo` makes one demo
account per role (password `demo1234`) and, into an inventory with no
products, three warehouses, suppliers, products with batches, variants and a
serial-numbered pump, and stock that got there through receipts.

## How stock is kept

- **A balance** (`nbin_stock`) is one product, in one location of a
  warehouse, of one batch (or none): `on_hand`, and the `damaged` part of it.
- **Every change** to a balance is a **movement** (`nbin_movements`), written
  by `stock.py` in the same transaction. Nothing else changes a balance, so
  the movements are the audit trail and always add up.
- **Reserved** (confirmed orders), **allocated** (orders being picked) and
  **in transit** (transfers on the road) aren't stored: they're read off the
  documents, so they can't drift.
- **Available** = on hand − damaged − reserved − allocated.
- Stock goes out **first expired, first out** unless someone picks a batch.
- A product is **low** when what's available is at or below its reorder point
  (or under its minimum), counted across every warehouse, and **out** when
  nothing is available.

## Documents and their steps

| Document | Steps | Numbers |
|---|---|---|
| Purchase order | draft → ordered (approved and placed) → partial → received, or cancelled | PO-2026-00001 |
| Receipt | posted once: stock in, batches and serials recorded, the PO fills up | RC-… |
| Order (sale, internal, department, project, distribution) | draft → confirmed (reserved) → picking (allocated) → issued, or cancelled (released) | SO-… / IS-… |
| Transfer | draft → requested → approved → in transit → received, or cancelled | TR-… |
| Adjustment | posted at once by an approver, otherwise pending → posted or rejected | ADJ-… |
| Count | open → submitted → approved (the differences become an adjustment), or cancelled | CNT-… |

## Roles

Permissions are `<area>.<action>` (`permissions.py`). The roles it starts with:

| Role | View | Receive | Adjust | Transfer | Approve |
|---|---|---|---|---|---|
| Administrator | ✓ | ✓ | ✓ | ✓ | ✓ (and users, roles, activity log) |
| Warehouse | ✓ | ✓ | Limited: theirs wait for approval | ✓ (request, dispatch, receive) | — |
| Purchasing | ✓ | ✓ | — | — | ✓ (POs, transfers, adjustments, counts, orders) |
| Sales | ✓ | — | — | — | — (writes customer orders) |
| Auditor | ✓ | — | — | — | — (reads the activity log) |

Administration → Users & roles changes them, or makes new ones.

## Accounts

There is no sign-up page. The first account comes from the command line;
after that, from Administration → Users.

| Command | Does |
|---|---|
| `uv run python -m modules.inventory.tools.users add --email … --name "…" [--role Warehouse]` | Makes an account (Administrator unless `--role` says otherwise); asks for its password |
| `uv run python -m modules.inventory.tools.users list` | Lists accounts |
| `uv run python -m modules.inventory.tools.users demo` | Demo accounts and demo stock (development only) |
| `uv run python -m modules.inventory.tools.users password --email …` | Sets a new password; ends that person's sessions |
| `uv run python -m modules.inventory.tools.users disable --email …` / `enable` | Switches the account off or on |

For scripts, set `BISHNOI_NEW_PASSWORD` instead of typing the password.

## Settings (`.env`)

| Setting | What it is | Default |
|---|---|---|
| `DATABASE_URL` | This app's own database | `sqlite:///.data/inventory.db` |
| `SESSION_HOURS` | How long a sign-in lasts | `10` |
| `EXPIRY_WARNING_DAYS` | A batch expiring within this many days is flagged | `90` |
| `DEAD_STOCK_DAYS` | Nothing issued or transferred out for this long counts as dead stock | `180` |
| `ORG_NAME`, `ORG_CURRENCY`, `ORG_LOCALE`, `ORG_TIMEZONE` | The company, as the screens show it | Bishnoi One, PHP, en-PH, Asia/Manila |
| `ALLOWED_HOSTS` | Host names this API answers to | `["localhost", "127.0.0.1"]` |
| `CORS_ORIGINS` | Browser origins allowed to call it directly | none |

## Deploying

Inventory goes online with the one backend (MAINTAINING.md, "Putting it online"): one Coolify
application for every module, on one PostgreSQL, where every table it makes starts with `nbin_`. Each
company has a database of its own beside it.

## Where things go

| Path | What it's for |
|---|---|
| `stock.py` | The one place stock changes: movements, FEFO picking, batches, serials, document numbers |
| `levels.py` | Every quantity (on hand, available, reserved…) and the low/out state |
| `routers/catalog.py` | Products (variants, specifications, pictures, supplier prices), categories, brands, units |
| `routers/warehouses.py` | Warehouses and their locations |
| `routers/stock.py` | Stock overview, movements, batches & expiry, serial numbers |
| `routers/purchasing.py` | Suppliers, purchase orders, receiving, backorders |
| `routers/orders.py` | Orders, reservations, issuance |
| `routers/transfers.py` | Transfers between warehouses |
| `routers/adjustments.py` | Adjustments and inventory counts |
| `routers/insight.py` | Dashboard, alerts, and the reports (with CSV export) |
| `routers/admin.py` | Users, roles & permissions, the activity log |
| `permissions.py` | Every permission, and the starting roles |
| `models.py` | The tables; changes go through a migration in `migrations/versions` |
| `server.py` | The app for hosts that import it (Vercel) |
| `tests/` | Tests (`uv run python -m pytest modules/inventory/tests`) |

Port: none of its own: it answers under its path in the one backend (port 8300), and its screens are in the one app (port 4301).
