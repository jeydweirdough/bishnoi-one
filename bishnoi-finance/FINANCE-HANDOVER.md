# Finance: handover for merging (as of 2026-10-24)

For Jade, from the Finance work on branch `feature/finance-safe-improvements`. It says what the branch adds to Finance, how it is built, where it stands against main's one-app change (`61a34b3`), what to watch for when merging, and what's still planned.

**⚠ Before the next deployment:** main now carries Finance migrations **0013–0020**. The next deploy of Finance's API runs them on the online Finance database (they add tables and columns in place; nothing is deleted except retired permission ticks; see §3). Please take a backup of that database first.

**In one paragraph:** since 5 Oct, all Finance work had been on our branch only; it reaches main with this push. It adds journal approval, notifications, a per-person calendar, e-signatures, the BIR Sales DAT screen, downloads, chart import, payables (suppliers, bills with an approval flow, payment vouchers) and more. The API side is complete and merged with main's `61a34b3`, Platform roles included; tests pass. The screens are being moved from the old `bishnoi-finance/frontend` into `bishnoi-one-app/frontend/src/modules/finance` in batches. Batches 1–5 are done; **Payables (suppliers, bills, vouchers) is the one left** (batch 6). Finance migrations run **0013–0020** on our branch; main's newest is 0012.

---

## 1. Where the code is

| | |
|---|---|
| Branch | `feature/finance-safe-improvements`; **pushed to `main` on 2026-10-24 at your request** (a fast-forward from `61a34b3`, nothing of yours changed) |
| Commits since `61a34b3` | `87b8130` payment vouchers + bill approval flow (0.4.12–0.4.13) · `8edb03d` merge of main `61a34b3` · `8944202` batch 2 · `f4bb085` batch 3 · `c8b4c23` batch 4 · batch 5 (Calendar, Sales DAT) + this handover |
| Backup branches | `backup/finance-before-one-app-2026-10-24` (= `87b8130`, last state with the old frontend), `backup/finance-before-main-merge-2026-10-23`, `-2026-10-22`, `backup/finance-before-bishnoi-merge` |
| Our old screens, for anything not yet moved | `git show 87b8130:bishnoi-finance/frontend/<path>` |
| Version | Finance's own numbering: 0.4.0 = everything of 22 Oct, then +0.0.1 per change; latest **0.4.13**. List: `src/modules/finance/version/changes.ts` (What's new page) |
| User guide | `bishnoi-finance/FINANCE-GUIDE.md` (written for the finance team; addresses still the old app's: updated in batch 7) |

Commits not on main (oldest last): `87b8130` vouchers + bill flow · `8fbaf82` payables, chart and supplier import, invoice reissue, tax messages · `d217fa2` no false build warning · `4dc3fe3` e-signatures, journal vouchers, liquidation reports · `127d09a` calendar · `658c2c4` quieter notifications, approve several, PH working days · `8499d01` journal approval + notifications · `5ac0450` Deputy's Overview · `e955e11` BIR Sales DAT · `818c327` Overview per role · `215d420` CRM company on every call · `3997fe8` version + What's new · `4552bab` release/review by different people · `8fd6894`, `8e79ec6`, `1ac4b51`, `582c944`, `7582970` (Oct 5: tests, guide, search + CSV downloads).

---

## Current local status — 26 October 2026

This dated update supersedes the older pending-work statements below.

- One-app screen batches 1–6 are complete on `feature/finance-safe-improvements`;
  Payables moved in `3f30dcd`. Existing branch commits were pushed at `69d6965`.
  Do not rebuild or move the Payables screens again.
- Local, uncommitted 0.4.14: bill-line purchase types with migration 0023 (JSON
  backfill inside existing bill lines), CASH descendants in disbursements/bank
  reconciliation, and Payables form-filler compatibility attributes.
- Local, uncommitted 0.4.15: permission-based Payables work queues on Overview,
  current-day AP aging at `/finance/bills/aging`, supplier/bucket drilldowns and
  CSV. Amounts owed, reserved in open vouchers and available to prepare remain
  distinct. No A+B migration or changes to approval/release rules.
- [Offline learning guide](../docs/finance-learning-guide.html) covers input
  lifecycles and section interactions. Permission-specific lessons are later.
- Last implementation checks: 45 affected backend tests, 24 Finance screen
  tests, one-app type check and five-account server-render/download checks passed.
  Browser visual/keyboard/zoom acceptance remains outstanding; HTTP checks are
  not a substitute. Local version is not a deployment claim.
- Batch 7 documentation is updated in this review. Central-role adoption,
  real staff rollout and deployment remain separate decisions. No commit/push
  of the new local work has been requested.
- An earlier fetch failed on GitHub DNS; the retry during this review succeeded
  (26 October). `origin/main` remained `0b2a686`, with no missing main commits.
  Fetch again before a later merge or commit rather than relying on this snapshot.
- Review follow-up: 26 targeted Calendar/signature/export/Sales DAT backend
  checks and 55 five-account HTTP page/access/download checks passed. Current
  local permissions, rather than older role descriptions, governed access checks.

## 2. Against main's one-app change (`61a34b3`)

**Merged as `8edb03d` with `git merge -X no-renames`.** Without it, Git's rename detection treats main's moved Finance files as renames and half-applies our old screens into the one app *unconverted*, and puts two of our files (`lib/tin.ts`, the account page) into the **Admin** module because they look alike. **Please merge our branch with `-X no-renames` too**, or the same happens.

After the merge: the one app was left exactly as main had it; our old `bishnoi-finance/frontend` was removed (as `check-apps` requires); our screens are moved in batches:

| Batch | What | State |
|---|---|---|
| 1 | The merge; the API keeps all ours + main's `platform_roles.py` | ✅ `8edb03d` |
| 2 | Bell (notifications), version footer + What's new, the Overview's sections | ✅ `8944202` |
| 3 | Journal approval, chart import + accounts under accounts, journal voucher print, ledger/statement/trial balance downloads, e-signatures (account page card, signature lines, Remove signature), Users' calendar switch | ✅ `f4bb085` |
| 4 | Marketing requests (liquidation report, download), invoices (cancel and reissue, clearer problems, TIN dashes), tax (On record, History), Price approvals fix | ✅ `c8b4c23` |
| 5 | Calendar, BIR Sales DAT (+ sidebar entries) | ✅ committed with this handover (checked by type check, tests and page loads; the finance team's own check still to come) |
| 6 | **Payables: suppliers (+ CSV import), bills (approval flow), payment vouchers (+ print)**, sidebar group, supplier CSV test | Complete on branch: `3f30dcd`; pushed with existing commits |
| 7 | Guide addresses, README note, What's new | Documentation updated 26 October; current local feature version 0.4.15 |

### How the screens are moved (so you can follow or continue it)
A converter applies the same rules main used for Finance; run on main's old Finance (`66087d2`) it reproduces main's one-app copy for **128 of 134 files**, the other 6 being your hand edits (`lib/api.ts`, `lib/apps.ts`, the frame, nav, the roles redirect, `profile-actions`).
- `src/X` → `src/modules/finance/X`; `app/(app)/X` → `app/(app)/finance/X`.
- Imports → absolute `@/src/modules/finance/...`.
- Page links (href, push, redirect, form action, crumbs, `FINANCE_NEEDS`) get `/finance` in front; `"/"` → `/finance` only where it's a link. **API calls are left alone** (`api.get("/finance/...")`, `load`, `fetchFile`, Finance's `send("patch", "/admin/users")`).
- Files changed on both sides: three-way merge (ours converted, main's old converted as base, main's one-app copy), so your hand edits stay. No conflicts so far.

Things the converter can't see, done by hand:
- **Links the API gives** (notifications, calendar items) are stored as the API names them (`/vouchers/…`, `/ledger?status=waiting`) and put under `/finance` **on screen**: `src/modules/finance/lib/links.ts` `screen()`. The API wasn't changed, so stored notifications keep working.
- The calendar's "About" page list (`calendar/types.ts` `PAGES`) is **stored with each event** in the API's form (`/bir/sales-dat`) and shown through `screen()`.
- `platform/lib/fail.ts` (removed from Finance by you) → the one app's shared `@/src/platform/lib/fail`.
- Finance's frame (`modules/finance/platform/app/shell-layout.tsx`) got a `footer` prop (passed to its `Nav`); the bell goes in your existing `ModuleActions bell` slot. `app/(app)/finance/layout.tsx` passes `<Bell>` and `<VersionFooter>`.
- **No one-app-wide setting was changed.** The upload limit you set (4.5 MB) covers our bill files; the Sales DAT engine import dropped its `.ts` ending (it needed `allowImportingTsExtensions`); the build stamp under the version (it needed `NEXT_PUBLIC_FINANCE_BUILD` in `next.config.ts`) is left out for now.
- Finance's screen tests moved to `src/modules/finance/tests/` with their own loader (`tests/support/resolve-ts.mjs` maps `@/` to the one app's folder and adds `.ts`). Not included by `tsconfig.json` (`.mjs`), not built by Next.

---

## 3. Backend architecture (what we added)

`bishnoi-finance/backend/app/`:

| File | What |
|---|---|
| `notify.py` | Notifications: `tell(db, people, kind, text, link)`, `done(db, kind, link)` (marks everyone's unread item about a link done), `holders(db, permission)`. `ACTIONABLE` kinds count in the bell's red number; `GROUPS` collapse several of a kind into one line. Never sent to whoever acted. Table `nbfi_notifications` |
| `signatures.py` | E-signatures: each person draws/uploads one on their account page (background cleaned in the browser); `sign(db, user, record_type, record_id, step, content)` records a signed step with a fingerprint of what was signed. Steps: prepared, approved, reviewed, settled, checked, released. Records: journal entries, fund requests, payment vouchers, bills (`SIGNED_RECORDS` in `routers/finance.py`). Tables `nbfi_signatures`, `nbfi_signed_steps` |
| `calendar_events.py`, `routers/calendar.py` | Per-person calendar (`calendar.use` is **per person**, `PER_PERSON` in `permissions.py`, switched on under Users, not a role tick): events, repeats, reminders (working days), sharing, done. Tables `nbfi_calendar_events`, `_shares`, `_done` |
| `workdays.py` | Philippine working days (uses the `holidays` package: added to `pyproject.toml`/`uv.lock`) |
| `bir.py` + `routers/finance.py /bir/sales-dat` | The BIR Sales DAT screen's server side (the converter itself runs in the browser: `modules/finance/bir/sales-dat`, Rommel's converter followed line by line) |
| `build.py` | The API's build (commit) for the version footer |
| `routers/exports.py` | CSV downloads: journal, account statement, trial balance, funds (`/finance/exports/...`), each needing its screen's view permission |
| `payables.py` | Bills' VAT and withholding worked out (`work_out`), the withholding codes (ATCs: WC158/WI158 1%, WC160/WI160 2%, WC120/WI120 2%, WC100/WI100 5%, WI010 5%, WI011 10%, WC010 10%, WC011 15%) |
| `routers/payables.py` | Suppliers (`/finance/suppliers`: add, edit, switch off, files, CSV import of Zoho's vendor export) and bills (`/finance/bills`: draft → submit → approve → check (only with tax withheld) → posted, ready to pay; return with a reason; void; files) |
| `routers/vouchers.py` | Payment vouchers (`/finance/vouchers`): several bills of one supplier, part of a bill allowed, never paid twice (open vouchers set aside what they hold), paid from an account under CASH; prepare → release (posts) → void; return/cancel; files; amount in words |
| `routers/finance.py` | Overview sections per role (`/finance/dashboard`), notifications (`/finance/notifications`), signatures, the frame |
| `ledger.py` | `post()` makes automatic entries (they count at once); sources: manual, fund, invoice, bill, voucher. Manual entries wait for approval (`status` waiting/approved/rejected; nobody approves their own; one "told first", others backup) |
| `routers/ledger.py` | Journal approval, chart import (`/accounts/import/check`, `/accounts/import`), accounts under accounts (`parent_id`), posting defaults (incl. payables, input VAT, withholding) |
| `routers/invoices.py` | Cancel and reissue (`replaces_id`), clearer problems, salesperson kept |
| `routers/tax.py` | Registration "On record" + History (from the audit log: which parts changed, never values), plain-language missing-field messages |
| `crm.py`, `config.py` | `CRM_COMPANY`: the company's short name sent on every call to the CRM |

Rules kept everywhere: permissions are `area.action` ticks (`permissions.py` `AREAS`; `AREA_LABELS` gives an area its own wording); every change audited (field names, not values); nobody approves their own request; whoever releases money doesn't check its liquidation.

### Permissions Finance declares (shown on the Platform's roles screen through `/platform/catalog`)
`dashboard.view` · `funds.view/release/check/settle/cancel` · `categories.view/manage` · `invoices.view/create/issue/collect/void/setup` · `suppliers.view/add/edit/deactivate` · `bills.view/create/approve/first/check/void` · `vouchers.view/prepare/release/void` · `journal.view/post/reverse/approve/first` · `accounts.view/manage` · `tax.view/manage` · `prices.view/approve` · `bir.prepare` · `admin.users/roles/audit`; per person: `calendar.use`.

### Database: migrations 0013–0020 (Finance only)
| | What |
|---|---|
| 0013 | Journal entries: `status`, decided by/at, rejected reason; `nbfi_notifications` |
| 0014 | Calendar tables; users' `calendar_on` |
| 0015 | `nbfi_signatures`, `nbfi_signed_steps` |
| 0016 | `nbfi_invoices.replaces_id` (once per invoice) |
| 0017 | `nbfi_accounts.parent_id`; `nbfi_suppliers`, `nbfi_bills`, `nbfi_bill_files`; payables / input VAT / withholding defaults; starter accounts 1300, 2300 |
| 0018 | Supplier details (Zoho's vendor fields, contacts JSON), `nbfi_supplier_files`; `suppliers.manage` split into add/edit/deactivate; `bills.record` also gets `bills.create` |
| 0019 | `nbfi_payment_vouchers`, `_lines`, `_events`, `_files`; bills' `paid_centavos`, `payables_account_id` (backfilled) |
| 0020 | Bills' approval stage and who approved/checked; `nbfi_bill_events`; `bills.record` and the voucher check/approve/first ticks retired; half-checked vouchers → to_release |

How they're written (please keep if you touch them):
- **Idempotent** ("only if not done": safe to re-run).
- **Columns added in place, never by rebuilding a table on SQLite.** A batch rebuild drops the old table and fires ON DELETE CASCADE / SET NULL on everything pointing at it (it emptied default accounts and journal lines in tests; 0013 and 0016 were fixed for it; `tests/test_migrate.py` proves rows survive an upgrade from 0012).
- Foreign keys added only on Postgres; record numbers `no` from 40000001 (a sequence on Postgres).
- **Numbering:** main's newest Finance migration is 0012. If main adds Finance migrations, they'd need to come after 0020 (or ours be renumbered: it happened once, on 22 Oct, when both sides made a 0012).

### Tests
- API: `cd bishnoi-finance/backend && uv run python -m pytest` → **239 passed** after merging `61a34b3` (ours + your 6 Platform-roles tests).
- Screens: `cd bishnoi-one-app/frontend && node --import ./src/modules/finance/tests/support/register.mjs --test "src/modules/finance/tests/*.test.mjs"` → **21 passed** (CSV readers, TIN, signature clean-up, version check, and the Sales DAT matched byte for byte against the original converter; that one needs the converter folder, `BIR_CONVERTER_DIR`, outside the repo, else it skips).
- `npx tsc --noEmit -p .` in the one app: clean after each batch.

---

## 4. Features, as the finance team sees them

- **Overview per role** (what waits on you, journal, calendar items, balances; Cristal's Deputy view).
- **Notifications** (bell): what's waiting on you or was done to your work; grouped; never for your own actions.
- **Journal**: manual entries wait for approval (the Finance Head told first, the Deputy backup); approve several; reverse; journal voucher print with e-signatures; automatic entries (marketing requests, invoices, bills, vouchers) count at once, their signatures being on their own documents.
- **Chart of accounts**: accounts under accounts; import Oojeema's or Zoho's CSV (checked row by row first, all or none).
- **Marketing requests**: release and review by different people; liquidation report with signatures; download.
- **Invoices**: cancel and reissue (the new one says which it replaces), clearer messages, TIN dashes.
- **Tax**: registration On record + History; messages that say what's missing.
- **BIR Sales DAT** from Oojeema's exports (Rommel's converter, for "Prepare BIR files").
- **Calendar**, per person, with reminders and sharing.
- **E-signatures** on the account page.
- **Payables**: suppliers like Zoho's vendors (+ CSV import of Zoho's export); bills with VAT and withholding worked out, the supplier's invoice attached ("Document missing" otherwise); **bill approval flow as Accounts Payable described it** (make + submit → Finance Head approves (Deputy backup) → BIR & Compliance checks only when tax is withheld → posted, ready to pay); **payment vouchers** (several bills, part-payments shown plainly, never paid twice, from an account under CASH, Oojeema and Zoho references kept, printable with amount in words and signatures, proof of payment, void by the Head).
- Price approvals only for roles with `prices.view`; downloads need their screen's permission.

---

## 5. With main's central roles (`platform_roles.py`)

- Finance still declares its ticks; the Platform shows them. At every sign-in Finance sets the person's role from the pass (`role_from` in `routers/auth.py`): an app admin → Administrator; a Platform role name matching a Finance role → that role; **anything else, or none → Finance Staff**.
- **Found 2026-10-24:** in Access → People, switching someone's Finance access off and on brings it back **without a role name**, so their next sign-in makes them Finance Staff (it happened to a test account, which then saw Price approvals). Worth keeping the role, asking for one, or warning.
- We haven't used "Bring in today's roles" yet; planned after the payables screens move (so the Platform becomes the master copy once, not mid-move).
- On our PC only: the Platform set up from its example (company `2mg` with Finance; Bishnoi One accounts for the Administrator and four test people, given Finance under Finance's role names, so no central roles yet).

---

## 6. Where a merge with your changes may conflict

- `bishnoi-finance/backend/app/main.py` (we include `exports.router`), `models.py`, `permissions.py`, `routers/finance.py` (includes the calendar, payables and vouchers routers, so `main.py` is otherwise untouched), `routers/auth.py`, `routers/admin.py`, `routers/profile.py`, `migrations/versions/` numbering.
- In the one app, Finance's own files we changed: `src/modules/finance/platform/shell/nav.tsx` (footer slot, `/finance/prices`, `/finance/bir`, `/finance/calendar` rules and entries; batch 6 adds the Payables group and an `also` list so a group stays open on its other addresses), `platform/app/shell-layout.tsx` (`footer`), `app/(app)/finance/layout.tsx`, `lib/types.ts` (`calendarOn`, `hasSignature` on Me), `components/admin.tsx`, `app/(app)/finance/account/page.tsx` (signature card), the screens of invoices, ledger, funds, tax, prices, finance-home.
- New folders only we add: `modules/finance/{notifications,version,dashboard,exports,signature,calendar,bir,lib/links.ts,lib/tin.ts,tests}`, `app/(app)/finance/{whats-new,calendar,bir,ledger/voucher,…/export,funds/[id]/report,funds/export}`.
- Suggested order: merge with `-X no-renames`; take both sides in the files above; run the 239 API tests, the 21 screen tests and the one app's type check.

---

## 7. What's still planned

1. **Bring in the Platform roles** as its own approved step; the screen move and batch 7 documentation are complete on this branch.
2. **Payables home and aging:** built locally in 0.4.15; visual acceptance and commit/push still pending. Historical-date aging is deferred; current balances are explicitly labelled.
3. **An ⓘ beside every screen's title** explaining the screen (Finance's page header only).
4. Later proposals: reminder to the backup bill approver after a working day;
   approve several bills; printable bill with signatures; offline bill drafts.
   Supplier 2307s, withholding summaries and financial statement screens already
   exist in Jade's BIR reports and need validation rather than a duplicate build.
5. Waiting on others: Dispatch/Pharmacy invoicing in Finance and sending invoices to Zoho; opening balances from Zoho (a cut-off date); petty cash and SSS/PhilHealth/Pag-IBIG remittances; which number Zoho's invoices carry; how 2MG and GPI are companies on the Platform.
6. **Working rule for Finance plans:** Zoho Books is the baseline; each plan says what's confusing in Zoho's way and how we improve on it.

### Known findings, not fixed (older)
Reversal date not validated, and fund/invoice entries can be reversed from the journal · money columns are 32-bit · the platform pass doesn't check the company · Inventory CSV negatives become text · invoices: back-dating unchecked against the ATP and previous numbers; Receivables says "latest first" but sorts most-overdue first; the `?on=` ageing uses today's payments; void/take-off reversals are dated today; Take off needs `invoices.void`; migration 0007 assumes account 4000 exists.

---

## 8. Data and safety
- No real customer or personal data, converter files, or bank account numbers are in the repo. Local databases (`.data/*.db`) and `.env` files are git-ignored. Test names in tests are made up.
- Nothing is deployed from this branch; no live data was changed.
- Questions about this work: zie1203 (bermas.zictc@gmail.com).

## Print-layout update —26 October2026 (local0.4.16)
Finance-owned printing/{frame.tsx,print-action.tsx,print.css} supplies common branding/frame; existing page bodies remain authoritative.2MG asset copied to public/finance/brand/2mg-logo.jpg (original root2MGlogo.jpg preserved), existing Bishnoi mark copied beside it. Company branding uses cached Platform getAccount().company because Finance's local Org is generic bishnoi/Bishnoi One; no settings/roles/database changed. Other companies do not get2MG logo. Finance-local shell/sheet/actions/signature classes scope print CSS; no shared-kit/other-app stylesheet edits. Report/record print toolbar added; existing invoice/dedicated print actions reused, new/edit/settings forms do not get a new print action. Named A4 portrait/landscape pages, repeated table headers, totals once, signature-group breaks, applied-filter context and printed-time footer. No page-counter guarantee.24screen tests/type check,55HTTP role checks,17branded page renders/assets and component controller checks passed. Browser unavailable: actual PDF visual/pagination acceptance remains pending. Uncommitted/unpushed; no new migration.

### Supplier importer0.4.18
Approved phases1-4 retain existing inline UI and Finance kit. Frontend payables/csv.ts+import-review.ts+import.tsx; backend app/supplier_import.py and routers/payables.py. Existing/check endpoint accepts source rows plus temporary review decisions; final/import now accepts rows+confirmed and recomputes eligibility under a supplier writer lock. Old suppliers-only payload rejected,preventing bypass of explicit tax/TIN review. Existing DB fields only;no migration. Source identities separately deferred. Deploy paired frontend/API versions;no deployment performed here. Tax defaults are unconfirmed in preview;no VAT/ATC inference. Real file only read for aggregate mapping coverage;not imported.
