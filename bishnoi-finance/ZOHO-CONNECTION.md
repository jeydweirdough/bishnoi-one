# Finance’s dedicated Zoho connection (local phase 1)

This registers and authorises Finance’s separate read-only client. It does not import transactions or post accounting entries. Sales order creation/approval remains in the sales app; Pharmacy creates invoices in Zoho.

## Set up on your PC

1. Keep the new Client ID and Client Secret private. Do not paste them into chat, screenshots, source files or the browser.
2. Open PowerShell in the repository, then run:

   ```powershell
   cd bishnoi-finance/backend
   uv run python -m app.tools.setup_zoho
   ```

   Paste the ID and secret into the hidden prompts (nothing appears while typing). Choose `com` for the Zoho account shown at accounts.zoho.com. The helper preserves other backend settings, generates an encryption key if none exists, and saves values only in ignored `backend/.env`. It does not print them.
3. Restart **only the Finance API** so it loads the settings. If another person/agent owns that process, ask them to restart it. The startup command from the repository root is `npm.cmd run bishnoi-finance`; check port8303 before starting a second copy.
4. Sign in to Bishnoi One as a Finance administrator, or a role with **Finance connections → Add and edit** (`integrations.manage`). No existing staff grants have been changed by this feature. The Finance Demo account does not gain this automatically.
5. Open <http://localhost:4301/finance/integrations/zoho>, also under Finance → Settings → Zoho connection. Click **Connect Zoho**, review the five read permissions and authorise the intended company account.
6. Back in Finance, click **Check connection and organisations**, verify the organisation name/ID with Finance, and choose **Use this organisation**. This does not start an import. If the organisation includes GPI too, a reliable2MGtransaction filter is still required before the next phase.

The API Console client must be **Server-based** with:

- Homepage: `http://localhost:4301/finance`
- Exact authorised redirect: `http://localhost:4301/finance/integrations/zoho/callback`

Keep spelling, scheme, host and port identical (`localhost` and `127.0.0.1` are different redirect registrations). Start and finish authorisation in the same browser session within five minutes. If signed out, sign in and start a fresh attempt; codes are never carried through login redirects. An error, expired code, wrong region or denied consent requires a fresh attempt.

## Access and storage

Requested scopes: `ZohoBooks.salesorders.READ`, `ZohoBooks.invoices.READ`, `ZohoBooks.contacts.READ`, `ZohoBooks.customerpayments.READ`, `ZohoBooks.settings.READ`. Phase1 calls only the OAuth authorisation/token services and the read-only Books organisation list. Tokens are exchanged in backend request bodies, never URLs sent to our API. No business create/update/delete methods are implemented. The next phase will fetch orders, invoices, customer details and payments.

Tokens and temporary authorisation states are encrypted using Fernet in `.data/zoho-connection.enc` beside the local SQLite database, with an OS lock for atomic updates and cross-process refresh. They are bound to that database, client ID, region and redirect address. Keep `ZOHO_ENCRYPTION_KEY` safe: losing it makes saved tokens unreadable. Never replace the key or change client settings while a saved connection remains without planning reconnection. Protect the Windows account and backend folder; encryption does not protect against someone who can read both the key and token file.

**Disconnect locally** removes the saved tokens and pending attempts from this Finance instance. It does not delete Zoho records or revoke the grant on Zoho; to revoke there too, use Zoho Accounts’ connected-app controls for this dedicated Finance client. Reconnecting replaces the local connection after a successful token exchange and requires organisation confirmation again.

This phase intentionally refuses production/non-SQLite operation. Before deploying, implement a persistent shared secret store, distributed refresh coordination and a registered HTTPS callback with access-log query redaction. Next development callback logging is disabled and the proxy omits callback parameters from its last-page cookie/login return address. Hosting access logs must be configured separately before production. Transaction persistence/scheduling is a later phase pending Jade’s database setup; this local file must not become production storage by accident.

No real OAuth credentials, tokens or source records belong in Git, Obsidian or test fixtures. Automated tests mock Zoho; live authorisation can only be checked after you complete setup.

## Bounded mixed-company investigation (no import)

Run `uv run python -m app.tools.probe_zoho --start 2026-10-20 --end 2026-10-27` from the Finance backend. It uses the dedicated connection and explicitly selected organisation. Defaults: at most2invoice-list pages (100rows/page),30invoice details,8order details,12linkedinvoice details and60totalGETrequests. Requests are paced;401refresh retries count against the budget,429/errors stop instead of hammering Zoho. OAuth refresh may POST to the token service; business requests are GET only. No new rights are requested.

The tool keeps provider payloads in memory and prints only aggregate structural findings with hashed example handles. Do not add a raw-response output option or copy real customer records into Git/Obsidian. It groups explicit source salesorderIDs and follows related invoices within limits; related invoice dates may fall outside the initial window and are counted separately. Prefix2MG/GPI identifies investigation candidates, never legal ownership. No match in a limited sample is not proof mixed-company orders never occur. The report distinguishes pagination/detail limits and unresolved source links. Confirm actual per-invoice/line company rules before importing; source mirrors must not automatically create BIR/accounting postings.

## Saved Sales orders demo (0.4.24)

Finance → Sales orders now reads only saved source copies. The 2MG-related view includes orders with a saved linked invoice whose exact `cf_invoicing_from` choice is `2mg Incorporated`; All includes both companies and unattributed orders in the saved batch. `Getmeds Philippines Inc.` maps to GPI. Unknown/new values are not inferred from prefixes. Original numbers remain intact. The order detail separates the full SO total from saved 2MG-linked invoices and shows current source balances, attribution and missing link details. These are not posted accounting/BIR totals.

The initial local batch is bounded Q1 2026 coverage; the screen states its invoice-date range, saved time and partial coverage. All does not mean every historical Zoho record. Earlier local orders remain under Sales orders → Earlier local orders; local decisions do not apply to source copies. Existing `sales_orders.view` permission gates both source views; no user grants changed.

After a SQLite backup and migration0026, a maintainer can run this from the backend:

```powershell
uv run python -m app.tools.sync_zoho_orders --start 2026-01-01 --end 2026-03-31 --invoices 30 --orders 30 --pages 2 --requests 100
```

This uses paced read-only provider calls, an OS lock to prevent concurrent local syncs, and atomic source-only upserts keyed by organisation+document kind+ZohoID. Source fields are explicitly allowlisted; no bank metadata or arbitrary response/notes dumps are saved. No source IDs are replaced by invoice numbers. Missing/invalid reads are labelled as partial; prior saved records are retained. The CLI writes only `nbfi_zoho_source_documents` and `nbfi_zoho_source_runs` and does not create local SalesOrder/Invoice/JournalEntry records. These tables currently live in the ignored local Finance SQLite database; shared deployment/storage and background scheduling remain separate work.

## Current-month invoices, orders and local background updates (0.4.25)

Open Finance → Sales orders or Finance → Sales → Zoho invoices (`/finance/invoices/zoho`). Both default to this calendar month (October1–31,2026 during initial setup), offer company filters, search and pagination, and retain the Q1demo under the period selector. Existing accounting invoices stay at `/finance/invoices`, with a Zoho records link; no route/numbering/posting behavior is replaced.

The month loader reads all returned summary pages for **both** sales orders and invoices, including uninvoiced orders. It saves each page atomically, keyed by organisation/type/ZohoID. Summaries include totals, statuses and invoice balances/company fields; full lines and source links are enriched separately and explicitly marked pending/stale. Invoice company attribution still uses exact Invoicing From choices. A matching SO field is retained as an **order indication**, not confirmed invoiced sales; 2MG-related can include that indication and the row explains it. Unrecognised values are not classified from invoice prefixes.

Initial month summary scan and bounded full details:

```powershell
uv run python -m app.tools.sync_zoho_month --requests 100 --details 30 --daily-limit 500
```

Ongoing local worker, from the Finance backend:

```powershell
uv run python -m app.tools.sync_zoho_month --watch --interval 300 --requests 80 --details 2 --daily-limit 500
```

Only one source-sync process runs at a time. The worker checks after each five-minute wait (plus cycle duration); overlapping modified-time checkpoints fetch new/changed records and updates to already saved records. Incomplete page sweeps resume; a successful checkpoint advances only after all pages are committed. Unknown read outcomes do not delete old saved data. Source reads are paced and429stops the cycle. The local500requests/day allowance is a **self-cap**, not proof of remaining organisation-wide quota; Mans’s client shares Zoho’s organisation limits. At the cap, updates wait; source pages remain usable and show timestamps. Confirm actual plan/headroom before increasing it.

The worker currently persists until its process/PC stops, not through PC restart. It is local-only pending Jade’s shared database/secret store/production scheduler. To stop just this worker, create `.data/zoho-month-worker.stop`; remove that marker before starting it again. Do not stop another person’s processes. After the worker stops, records remain saved but freshness stops advancing.

Pages/API endpoints do **not** call Zoho or acquire its network/token lock. They read the local database and atomically saved organisation identity. Visible list pages re-read saved data about every60seconds when not hidden/typing. Thus a new upstream record is normally visible after a worker check plus page refresh, not instantaneously; quotas, failures and pending detail work may delay it. Full lines/tax/order relationships can lag summary availability. Preserved old line details are never presented as current after a changed summary.

Initial scan is a source snapshot, not a legal/accounting import. Hard-deletion reconciliation and complete older-history backfill are separate work; changed-record polling does not prove deleted records have been removed. Source records do not automatically feed Finance GL/receivables/BIR totals. No migration beyond0026was required for month sync; metadata/checkpoints use existing source-run JSON.


## PostgreSQL compatibility prepared — 0.4.29 (not an active database switch)

Finance supports an explicit `POSTGRES_DRIVER=pg8000` option with verified TLS and required SCRAM channel binding. The default psycopg option is retained for existing hosts. The Python-only option avoids this PC's blocked native driver without changing Windows security. Unsupported/insecure connection options fail closed; no credentials are echoed.

Migration0027 defines two initially empty tables: encrypted Zoho authorisation and shared updater/quota controls. Existing0023–0026 supply supplier review fields, Finance orders and source snapshots. No users, roles, accounts or financial records are copied by0027. PostgreSQL migration locking now encloses the schema changes on the same connection/transaction.

Actual connection remains SQLite during this stage. Do not replace DATABASE_URL yet. Private FINANCE_NEON_REVIEW_URL is only used by `uv run python -m app.tools.neon_preflight`; that command never starts the app, migrates or writes data, and checks the target in a read-only transaction. It has successfully checked the official0022target through the application SQLAlchemy driver.

PostgreSQL authorisation is deliberately opt-in: `ZOHO_DATABASE_ENABLED`, a stable `ZOHO_CONNECTION_ID`, `ZOHO_ENVIRONMENT`, the separate encryption key/client settings, and explicit `ZOHO_WORKER_ENABLED` after the reviewed switch. Tokens remain encrypted; keys stay outside the database. Changing passwords does not invalidate the environment binding; changing endpoint/environment/client/callback fails closed. Cloned storage never silently reuses the local token file. Reconnect once in the intended target after identity and setup checks.

Database workers use a renewable120second lease and database-time quota reservations before each source GET, including retries/failures; source writes are fenced against expired ownership, pause/disconnect or changed organisation. The500read cap remains Finance's own allowance, not the whole organisation's remaining quota. Pause/resume requires integrations.manage and is audited. Source lists read a snapshot of saved organisation identity without network/token-refresh locks. Source invoices remain separate from accounting invoices.

**Validation boundary:** synthetic SQLite state/concurrency/migration-preservation tests and actual SQLAlchemy/TLS read-only Neon connection checks passed. Full PostgreSQL migration/concurrency/write rehearsal is pending a disposable local PostgreSQL runtime; PostgreSQL server/Docker/installedWSL were not available here. Never run tests, ordinary API startup or copy_database against the official URL to fill that gap. No Neon test branch is required or requested.

Before official activation: verify recoverable backup, rehearse PostgreSQL migration on a disposable local target, preserve all existing target setup/identities, review local chart/vendor transfer, and obtain the separate cutover approval. File uploads, Platform identities and the existing SQLite encrypted connection are separate from table migration. No deployment or historical financial import occurs here.

### Current local runtime while compatibility is staged
The previous agent-started reloading Finance API was replaced by a private unchanged non-reloading runtime snapshot under backend/.data/neon-compat-runtime, still using the original backend/.env and original SQLite database/uploads. It serves port8303 and does not load compatibility edits. Platform/frontend were preserved. The current launcher is `.data/neon-compat-runtime/serve.py`, run with the backend's Python environment. RecheckPID/starttime before any process change.

Normal `uv run main.py` from the new source will discover0027 and attempt to migrate localSQLite on startup. Keep using the protected existing runtime during this preparation stage; normal restart/activation needs the planned backup and explicit local schema transition. The active SQLite database remains0026; source tests use temporary0027databases. This snapshot is local/ignored, not a deployment strategy.

## Active on this PC — 0.4.30, 2026-10-28

This supersedes the preparation-only status above. Full official backup, local restore, migration and full-startup preservation rehearsals passed before a fresh official backup and additive0022→0028upgrade. Every old row/column was preserved. Clean setup transfer added267accounts and1593imported directory suppliers;19existing accounts,3users and10roles retained. All SQLite test transactions and1manual/document supplier stayed local. Source cache/checkpoints moved separately; source copies still do not post Finance accounting/BIR entries.

| Use | Site | API and database |
|---|---|---|
| Official records | http://127.0.0.1:4302/finance |8313, Neon|
| Testing | http://localhost:4301/finance |8303, original SQLite; Zoho network/sending disabled|

Use these exact hostnames: different hostnames keep browser cookies separate; ports alone do not. No deployment, Platform grant change, account bulk copy, commit or push performed.

Private operational helpers/configuration live under backend/.data and remain ignored. Original.env retains local SQLite defaults; the explicit official launcher now reads the approved FINANCE_NEON_REVIEW_URL and separate private key. Do not run the generic database-copy tool over existing Neon setup.

Restart officialAPI from backend: `uv run python .data/run_finance_environment.py --official`. Local testingAPI: `uv run python .data/run_finance_environment.py`. Official reader: `uv run python .data/run_official_source.py`. Check ports/PID/start time first; never start duplicates or stop someone else's process. Reader waits five minutes between cycles, shares a DB lease/request allowance and pauses at its self-cap. Full details can lag summaries; pending count/freshness are visible. It is not a Windows service and stops when the PC shuts down.

Official site from frontend: set FINANCE_API_URL=http://127.0.0.1:8313, PLATFORM_API_URL=http://127.0.0.1:8305, FINANCE_OFFICIAL_PREVIEW=1; run `node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 4302`. The preview flag selects a separate ignored build directory. Keep Platform8305 and the regular local site4301running. Default frontend behaviour is unchanged.

Transferred OAuth remains READ-only, re-encrypted in Neon under a separate private key. Existing reads require no reconnect. Before future extra consent, add `http://127.0.0.1:4302/finance/integrations/zoho/callback` to the dedicated Finance client's authorised redirect URIs. Never publish keys/secrets. Preserve private database backups and encryption-key recovery material outside Git.

## Background delivery prepared; live sending OFF

Migration0028adds three empty tables: unique delivery jobs, verified local/Zoho identity links, delivery history. Final bill clearance and voucher release save a delivery intent atomically with the accounting change. Drafts, returned/unapproved records and historical transactions are not replayed. Bill/voucher details show delivery status separately; Settings → Zoho connection → Delivery queue shows counts and next steps. Queue administration uses integrations.manage; normal readers see only their permitted record's summary.

No HTTP handler sends bills/payments to Zoho. Bounded `app.tools.send_zoho` requires official PostgreSQL, explicit live flag and actual bills/vendorpayments READ+CREATE grants. It shares the reader's lease/quota. Stable references, pre-create checks, committed attempt markers and response verification protect identity/amounts/relationships. Timeout/5xx/crash uncertainty never blindly rePOSTs. `--reconcile <job-id>` checks an uncertain job using GET only, including with live sending off. Do not clear attempts or manually recreate uncertain records.

Before activation: match supplier/account/paid-through/VAT/company identities to Zoho; verify default money accounts and tax registration in official Finance. SQLite settings were not copied. Withholding bills/payments remain held until actual Zoho treatment is confirmed. No guessed tax defaults, remote vendor creation or automatic deletion. No outbound worker is running; no live bill/payment was sent by this work. Extra OAuth consent alone does not start sending.

For another host, configure real DATABASE_URL, supported POSTGRES_DRIVER, DATA_ENVIRONMENT=official, separate durable encryption key, ZOHO_DATABASE_ENABLED=true, stable connection/environment IDs, and one supervised reader. Enable capture explicitly; keep outbound off until reviewed. Tests must use a separate database; never point destructive TEST_DATABASE_URL tests at official Neon.
