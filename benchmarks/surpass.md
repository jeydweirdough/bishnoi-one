# Surpassing each benchmark

Drawn up on 2026-10-24. For every benchmark: what it does best, what we add
to do better **for a Philippine pharma distributor**, and the reports that
beat its own. Nothing here is built unless the matrix
([benchmark-matrix.md](benchmark-matrix.md)) says so; each item is
**proposed** until it's decided there. Two parts apply to everything and were
decided the same day: the **sidebar** (module switcher and process-oriented
menu, like Zoho One) and **trails and tracks** on every record and process.

Each feature names the module it lands in: CRM, Inventory (Inv), Finance
(Fin), Pharmacy (Ph), Admin, Platform (Plat), Regulatory (Reg), In-Licensing (IL).

---

## 1. How every module is laid out (decided 2026-10-24)

### 1.1 Module switcher, by access

- The top of the sidebar is the **module switcher**: the company's logo and
  the module you're in; open it to see **only the modules you have access to**
  (your role on the Platform gives you a module, or not), each with its icon
  and what it's for. One click moves you there, already signed in.
- A module the company hasn't been given isn't listed. A coming-soon module
  that was given shows, marked Coming soon.
- Your first module (the one you use most, or the first given) is where you
  land after signing in.

### 1.2 The menu follows the work, not the database

Each module's menu is grouped by **process**, in the order the work happens,
not by record type. Every group is a short flow, top to bottom. The table is
the target; what's built (2026-10-24) is in the matrix, J2, and a step that
isn't built yet joins its group when it is:

| Module | Groups, in order (each a process), in the terms Zoho uses |
|---|---|
| CRM | **Home** · **Customers** (Leads, Customers, Contacts) · **Sales** (Deals → Quotes → Order links → Sales orders) · **Field sales** (Team progress, Doctors, Routes, Visits, Patient assistance) · **Customer retention** · **Activities** (Calendar, Activities, Email) · **Products** (Products, Promotions, Bundles, Special prices) · **Marketing** · **Reports** |
| Inventory | **Home** · **Items** (Products, Product registrations, Categories, Brands, Units) · **Inventory** (Stock on hand, Batches and expiry, Serial numbers, Transfer orders, Stock movements, Warehouses) · **Inventory control** (Stock counts → Inventory adjustments) · **Sales** (Orders → Packages → Shipments) · **Purchases** (Suppliers → Purchase orders → Goods receipts → Supplier returns) · **Reports** |
| Finance | **Home** · **Sales** (Invoices → Receivables → Payments received) · **Expenses** (Pending release → Pending liquidation review → Pending settlement) · **Purchases** (Suppliers → Bills → Payment vouchers) · **Cash advances** · **Approvals** · **Accountant** (Journal entries → Trial balance, Chart of accounts) · **Banking** (Bank reconciliation) · **Taxes** (VAT return, Withholding tax, Summary lists, BIR files) · **Reports** (Financial statements, Books of accounts) |
| Pharmacy | **Home** · **Dispensing** (Prescriptions → Dispensing → Sales) · **Customers** · **Inventory** (Medicines, Batches and expiry, Stock, Suppliers, Recalls) · **Approvals** · **Reports** |
| Admin | **Home** · **Compliance** (Renewal alerts, Permits, Documents, Expatriates, Properties) · **Fleet and travel** · **Service requests** · **Marketing** |
| Regulatory (soon) | **Registrations** (Applications → FDA filing → CPR issued) · **Renewals and variations** · **Permits** · **Recalls** |
| In-Licensing (soon) | **Principals** · **Products** · **Agreements** (Terms → Agreement → Signed) · **Launch** (Registration → First order) |

**Setup** (what the module needs before work starts, with a red count of
what's missing) and **Administration** (users, roles, activity log) stay at the
foot of every menu. Labels are the standard terms Zoho uses (Sales, Purchases,
Accountant, Banking, Taxes, Pending actions), never casual verbs.

### 1.3 Directive: the sidebar says what to do next

- **Pending actions**, on every module's dashboard (Home), not in the sidebar: what's waiting for *this
  person* (quotes to approve, bills to check, CPRs expired, transfers to
  receive), each a row with its count, linking to the filtered list. Nothing
  waiting, and it says so. Same source as the bell.
- **Counts on the steps**: each step of a flow shows how many records sit
  in it (Quotes 4 waiting); a step with something overdue is red.
- **Set-up checks**: what a module needs before it can work (invoice
  numbers, posting accounts, CPR numbers) shows as a red mark on the step
  that needs it, with the sentence saying what's missing.
- **One primary action per page** (New quote, Record bill), and after saving,
  the next step's button (Quote saved → Send for approval / Make order).
- **Empty states offer the next action** for the person's role (see the
  memory rule "controls sit with their target").
- Collapses to icons (the rail), remembered across modules; on a phone it
  slides in over the page.

### 1.4 Trails and tracks, on everything

- **Trail** (per record): who did what and when, in plain words, newest
  first: made, changed (which fields), approved, returned with the reason,
  posted, voided, printed, emailed, opened by the customer. Read from the
  audit log every app already keeps, plus the record's own events. Shown on
  every main record's page (a Trail tab, or the right-hand column), and
  filterable by person and kind. Values stay out unless a field opts in (B3).
- **Track** (per process): where a record stands in its flow, drawn as
  steps (Draft → To approve → Approved → Posted), the step it's on lit, with
  who has it and since when, and how long each step took. On every record that
  moves through steps: deals, quotes, orders, purchase orders, transfers,
  adjustments, bills, vouchers, invoices, marketing requests, prescriptions,
  registrations.
- **Process reports from tracks**: average time in each step, what's stuck
  longest, who it's waiting on: one report per module (see each benchmark
  below for the ones that beat theirs).

---

## 2. Salesforce: the metadata platform

**Best at:** custom objects and fields without code, layouts per record type,
validation rules, report types, Chatter.

**To surpass it:**
- Custom fields, layouts and validation rules in **every** module, not only
  the CRM (A6, A7, A8), set by the company's admin, kept as data.
- Duplicate rules split from what happens (warn, block, merge) and a
  **merge** that keeps both records' trails (A5).
- A feed on every record (C3) that is the **trail** above plus people's notes
  and @mentions, so history and conversation are one place.
- Flows without code: "when a quote is approved, make the order and tell the
  warehouse" (H1), each run on the record's trail.

**Reports that beat it:** saved views become reports with a chart in one click
(E1, E2); **every report has a "why" drill-down** to the records; scheduled
email of any report to a person or team; **report on tracks** (time in stage,
stuck deals by owner) without building a report type.

## 3. SAP: master data and pricing

**Best at:** pricing conditions, credit management, change documents,
effective-dated organisation.

**To surpass it:**
- Price conditions as today (F4), plus a **price simulator**: pick a customer
  and products and see every condition that applied and why, before quoting.
- Credit control as today (E6), plus **credit holds released on payment**
  automatically when Finance records it.
- Effective-dated team membership and ownership (G5): "who owned this in
  March" answered on every report.
- Value history on chosen fields (prices, credit limits, CPR dates) on the trail.

**Reports that beat it:** price realisation (list vs. what we sold at, by
customer, rep and product); margin by product, customer and team with
Finance's costs; credit exposure (limit, owed, overdue, on order) per customer
with the trend; condition usage (which promos and discounts actually ran).

## 4. Odoo: one timeline, views, documents

**Best at:** the chatter on every record, activities, one list as table,
board, chart, pivot; QWeb documents; automated actions; portal.

**To surpass it:**
- One timeline on any record (C1) that merges the trail, activities, emails,
  calls and the customer's portal actions.
- Every list as table, board, **chart and pivot**, saved per person or shared (E1).
- Documents (PDF) from the same data the screens use (E4): quotes, invoices,
  delivery receipts, 2307s, vouchers, in the company's own template.
- A customer portal (H2): their orders, invoices, statements, 2307s to
  upload, and re-ordering, each step on the record's trail.

**Reports that beat it:** pivot on any list with export; **activity
completion** by person (planned vs. done, overdue); automated-action log
(what ran, on which record, what changed).

## 5. Marg ERP: distribution, batches, schemes, receivables

**Best at:** fast grid entry, batch and expiry, schemes, outstanding and
ageing, GST, van selling.

**To surpass it:**
- Grid entry with the keyboard on orders, receipts and invoices (G2), with
  batch and expiry picked FEFO as you type.
- Schemes as today (F6) plus **scheme cost** charged to the promo and
  shown against what it sold.
- **CPR and FDA rules on sale**: no order line for a product whose CPR has
  expired (G7, once decided), Rx lines need the prescription.
- Collections in the field offline (G3), receipts printed or sent from the phone.

**Reports that beat it:** near-expiry by customer (what they hold that we
sold them, to take back before it expires); batch traceability (one batch:
received from, stored where, sold to whom, returned); ageing with promised
dates and the collector's notes; scheme performance (cost vs. extra sales);
**CPR status** of everything on hand and on order.

## 6. Veeva: life sciences field work

**Best at:** structured calls, call plans, samples, compliant field work.

**To surpass it:**
- Calls and plans as today (C4, C5), plus **sample management**: samples
  issued from Inventory to the rep, given to the doctor on the visit with the
  doctor's signature, the rep's stock reconciled monthly.
- **Patient assistance** as today, tied to the products the doctor prescribes.
- Doctor consent and data-privacy record (Data Privacy Act) on the trail.

**Reports that beat it:** reach and frequency against the tier plan; message
recall (which key messages land, by product and specialty); sample
accountability (issued, given, returned, missing) per rep; prescriptions
influenced (PAP approvals and orders after visits).

## 7. HubSpot: associations and the everyday CRM

**Best at:** associations, sequences, inbox, simple reporting, ease of use.

**To surpass it:**
- Associations as today (A10), plus **sequences**: a set of emails and
  tasks a rep enrols a customer in, stopping when they reply or order.
- Reply from the Lead inbox (C8) on every channel, with the conversation on
  the customer's timeline.
- Lead scoring from what the customer did (opened, replied, ordered,
  visited), shown as a number with its reasons.

**Reports that beat it:** source to cash (which channel brought customers
who then paid invoices, via Finance); sequence performance; response time on
the inbox by person and channel.

## 8. Zoho (One and the Zoho apps): the suite and its sidebar

**Best at:** one sign-in across many apps, a sidebar that switches apps and
keeps each app's menu short, settings searchable, blueprints (a process drawn
as states with who moves it).

**To surpass it:**
- The switcher shows **only what you may use** (above), with the waiting
  count of each module on its row, so you know where work is before you go.
- **Blueprints as tracks**: each process's steps drawn once and used for
  the record's track, its approvals, the sidebar's counts and the stuck report.
- One search across every module you have (G2 across apps), by your access.
- Settings found by search ("invoice numbers", "CPR").

**Reports that beat it:** one Home across modules for an executive (sales,
collections, stock risk, CPR expiry, filings due) read from each module's own
figures; cross-module process report: quote → order → issued → invoiced →
paid, with the days between each.

## 9. Oojeema: Philippine BIR accounting

**Best at:** BIR books, forms and lists, DAT files, Philippine practice.

**To surpass it:**
- Everything in F9 today, with every figure **traced** to its records (click a
  2550Q line, see the invoices and bills).
- A **BIR calendar**: each form's due date, prepared or not, filed or not,
  with the filing reference kept (the trail of the filing).
- 2307s received from customers matched to their payments automatically; the
  ones still missing chased.
- The remaining DAT files (SLS, SLP, SAWT, QAP) once BIR's layouts are confirmed.

**Reports that beat it:** VAT reconciliation (books vs. return vs. lists);
missing 2307s by customer; withholding due by month; a filing status board
for the year.

## 10. Twenty: the modern open CRM

**Best at:** clean views, command menu, boards, speed.

**To surpass it:** what we built after it (E1, E2, G2), plus keyboard
everywhere (every list, every form), and the same feel across every module
through one kit and one sidebar.

---

## 11. Reports, by module (the full set to reach)

Built 2026-10-25 on the shared kit, every module (see the matrix's E3): Inventory 17, CRM 14, Finance 12, Pharmacy 14, Admin 14, each grouped in the sidebar's Reports area and shown only to roles that may open the data. Still to add:

| Module | Reports to add (beyond what's built) |
|---|---|
| CRM | Source to cash; price realisation; margin by customer/rep; reach and frequency vs. plan; message recall; sample accountability; sequence performance; inbox response time; time in each deal stage; stuck quotes |
| Inventory | Batch traceability; near-expiry held by customers; CPR status of stock on hand and on order; fill rate per order; picking time; supplier lead-time trend; count accuracy |
| Finance | VAT reconciliation; missing 2307s; withholding due; filing status board; cash forecast from receivables and bills; collection effectiveness (CEI); expense by marketing request outcome; time to approve bills and journals |
| Pharmacy | Dispensing time per step; verification rejections by reason; controlled drugs register; recalls traced to patients |
| Admin | ~~Permits and licences expiring~~ (built 2026-10-25: Renewals due, Expired and not renewed); compliance calendar as a calendar view |
| Every module | **Time in each step and what's stuck** (from tracks); **who did what** (from trails), by person and period |
