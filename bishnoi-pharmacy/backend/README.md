# Bishnoi One Pharmacy — API

The Pharmacy app's own backend. Its screens are in `../frontend`.

It has **its own sign-in**. Accounts live in this app's own database, and an
account here signs in to this app only.

## The order of work

```
Prescription received ──> Checking ──> Verified ──> Dispensing ──> Sale
                              │           (queue)    (batch picked)  (recorded)
                              ├──> Needs clarification ──> checked again
                              └──> Rejected (closed)
```

- **Checking comes first, and apart from dispensing.** A pharmacist ticks ten
  checks (patient, prescriber, date, medicine, strength, dosage form,
  quantity, directions, required details, availability), matches each
  medicine as written to the catalogue, and gives a verdict. Verified needs
  every tick and every match, and nothing blocking: a date in the future or
  older than `PRESCRIPTION_VALID_DAYS`, an inactive medicine, or a dangerous
  drug without the prescriber's licence number. Clarification and rejection
  need a note.
- **Only a verified prescription can be dispensed.** Dispensing picks the batch
  each unit comes from (the soonest-expiring first); only an *eligible* batch
  can be picked: available (not quarantined or recalled), unexpired, and in
  stock. Less than owed is fine: the prescription is then partly dispensed and
  waits for the rest.
- **Every dispensing records its sale.** Counter sales are for over-the-counter
  medicines only; a prescription medicine at the counter is refused.
- **Every change to stock is a movement** (received, dispensed, sold, adjusted,
  returned) with the balance after it, so what's on hand can be explained.

## Running it

```
cp .env.example .env
uv sync
uv run python -m app.tools.users add --email you@example.com --name "Your Name" --admin
uv run main.py          # http://127.0.0.1:8307  (docs at /docs)
uv run pytest
```

The database is brought up to date on every start (`app/migrate.py`, Alembic
migrations in `migrations/versions`). SQLite in `.data/` unless `DATABASE_URL`
says otherwise; Postgres works the same (Neon, Supabase's pooler on port 6543).
A SQLite file is copied beside itself before a migration touches it, and put
back if the migration fails.

Every table is **`nbph_…`** (Bishnoi One PHarmacy), and so is the migration table,
`nbph_alembic_version`. A database from Orbit Pharmacy (plain `users` and
`sessions`) has its accounts carried over by the first migration.

## Accounts and roles

There is no sign-up page. Accounts are made in Administration → Users, or from
the command line:

| Command | Does |
|---|---|
| `uv run python -m app.tools.users add --email … --name "…" [--admin] [--role "Pharmacist"] [--license PRC-…]` | Makes an account; asks for its password |
| `uv run python -m app.tools.users list` | Lists accounts |
| `uv run python -m app.tools.users demo` | Demo accounts, catalogue, stock, patients and prescriptions in every state; password `demo1234` (development only; `app/demo.py`) |
| `uv run python -m app.tools.users password --email …` | Sets a new password; ends that person's sessions |
| `uv run python -m app.tools.users disable --email …` / `enable` | Switches the account off / on |

On a host you can't run commands against (Vercel), set `FIRST_ADMIN_EMAIL` and
`FIRST_ADMIN_PASSWORD`: the first start makes that administrator, only while
there are no accounts at all.

It starts with three roles (Administration → Roles & permissions changes them,
or adds more):

| Role | Does |
|---|---|
| Administrator | Everything, including users, roles and the activity log. Can't be changed. |
| Pharmacist | Checks and verifies prescriptions, dispenses, runs the stock. No administration. |
| Pharmacy Assistant | Takes prescriptions in, keeps patient records, sells over the counter, receives stock. Doesn't verify or dispense. |

Permissions are `area.action` (`app/permissions.py`); `prescriptions.verify`
and `dispensing.create` are separate on purpose.

## Endpoints

| Prefix | What |
|---|---|
| `/auth` | Sign in, out, `me`, demo accounts (development) |
| `/dashboard`, `/reports/{prescriptions,dispensing,sales,usage,expiry,stock}` | What needs doing; reports over `from`/`to` |
| `/prescriptions` | Inbox, pending, verified, attention, history; receive; correct; `POST /{id}/check` |
| `/dispensing` | `queue` (queue, partial, dispensed), `prepare/{rx}`, dispense, history |
| `/sales` | Today and history, counter sale, `/{id}/returns`, `/returns` (returns, refunds) |
| `/patients` | Patients and customers, with prescription and medication history |
| `/medicines` | Catalogue, `categories`, `brands`, each medicine's batches |
| `/batches` | All, expiring, expired, held; `/{id}/status` (quarantine, recall, release) |
| `/stock` | Current, low; `receivings`, `adjustments`, `movements` |
| `/suppliers` | Who the pharmacy buys from, and their deliveries |
| `/admin` | Users, roles and permissions, the activity log |

Send the token as `Authorization: Bearer <token>`. The database keeps only a
hash of each token. Passwords are hashed with scrypt. Five wrong passwords for
one email make it wait 15 minutes.

## Settings (`.env`)

| Setting | What it is | Default |
|---|---|---|
| `DATABASE_URL` | This app's own database | `sqlite:///.data/pharmacy.db` |
| `FIRST_ADMIN_EMAIL`, `_NAME`, `_PASSWORD` | The first administrator, for an empty database | none |
| `SESSION_HOURS` | How long a sign-in lasts | `10` |
| `EXPIRY_WARNING_DAYS` | A batch expiring within this many days is "expiring" | `90` |
| `PRESCRIPTION_VALID_DAYS` | Older prescriptions can't be verified | `180` |
| `ORG_NAME`, `ORG_CURRENCY`, `ORG_LOCALE`, `ORG_TIMEZONE` | The company, as the screens show it | Bishnoi One, PHP, en-PH, Asia/Manila |
| `ALLOWED_HOSTS` | Host names this API answers to | `["localhost", "127.0.0.1"]` |
| `CORS_ORIGINS` | Browser origins allowed to call it directly | none |

## Where things go

| Path | What it's for |
|---|---|
| `app/models.py` | Every table, `nbph_…` |
| `app/stock.py` | Taking stock off a batch and putting it back: the one way it's done |
| `app/permissions.py`, `app/access.py` | What a role may do, and the check on each endpoint |
| `app/routers/` | One file per area |
| `app/api.py` | What routers share, including record numbers (RX-2026-00125) |
| `app/audit.py` | The activity log |
| `migrations/versions/` | Changes to the tables |
| `tests/` | Tests (`uv run pytest`) |

Port: screens on 4307, this API on 8307 (screens + 4000).
