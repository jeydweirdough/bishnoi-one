# Benchmark matrix

One row per capability. **Reference** is the benchmark we match for it (see
[best-of-breed.md](best-of-breed.md)). **Ours today** is what the code does
now. **Decision** is ADOPT, ADAPT, HAVE, SKIP or `open` (see
[README.md](README.md)); a *proposed* decision is a suggestion until someone
who owns the product makes it.

Row IDs don't use the letter D, which the decisions use (D2, D4, D7, D8
and ICP, all decided on 2026-09-25: see [decisions.md](decisions.md)). A row
settled by one of them names it.

## Where each app stands

"Ours today" names the apps with features: **CRM**, **Inv**entory,
**Ph**armacy, **Plat**form, and **Finance**, which so far has only the tax
engine (F8, F9). **Admin, In-Licensing and Regulatory** only have sign-in,
so every row is *none* for them; they start from this matrix.

Links between apps today: the CRM takes its products and stock from
Inventory, and its tax from Finance.

Checked against the code on 2026-09-25. Update a cell in the same pull
request that changes what it describes.

---

## A. Records and data

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| A1 | One party with roles (customer, supplier… are roles on one record) | SAP ★ | Ph partial: patients and customers share `nbph_patients` (`kind`); suppliers are separate. CRM, Inv: separate tables. | open (proposed ADAPT: one party table per app, roles on it, before a second party table is added anywhere) |
| A2 | Record numbers people can say out loud | ours | CRM `PREFIX-YYYYMM-####` (prefix set in its settings); Inv `PO-2026-00421`; Ph `RX-2026-00125`; Plat `BUG-2026-00421`. | open (proposed HAVE; align CRM to `PREFIX-YYYY-#####`) |
| A3 | Archive, never delete; refuse to delete what has history | ours | CRM, Inv, Ph: switch-off / discontinue, delete refused when in use. Plat: not checked. | open (proposed HAVE) |
| A4 | Import (CSV/XLSX) and bulk actions | Salesforce | CRM: import wizard (`routers/imports.py`) and bulk jobs (`routers/bulk.py`). Inv, Ph, Plat: bulk-selection UI in the kit, no import or bulk routes. | open (proposed ADAPT: CRM's import and bulk into the shared kit) |
| A5 | Duplicate and matching rules (what's a match, separate from warn or block) | Salesforce ★ | CRM: warns on save and allows an override (companies, contacts); fixed matching, no warn/block setting. Others: none. | open (proposed ADAPT: split matching from the action) |
| A6 | Custom fields as data, with no migration | Salesforce ★ | CRM: admin-made fields and sections (Settings → Forms, `extra` JSON on companies, contacts, products, quotes). Inv partial: free `attributes` JSON. Ph, Plat: none. | open (proposed ADAPT: CRM's forms become the kit's, for every app) |
| A7 | Layouts and required fields per record type | Salesforce ★ | CRM partial: one layout per entity, required/hidden per field, not per customer type. Others: none. | open |
| A8 | Declarative validation rules, errors on the named field | Salesforce ★ | Every app: rules in code (pydantic); errors already come back on the named field. CRM partial: admin-set required fields and options. | open (proposed ADAPT: keep code rules, add admin rules on custom fields) |
| A9 | Extend a record without forking its code | Odoo ★ | None: each app is its own codebase. | open (proposed SKIP: each app owns its code) |

## B. Access and history

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| B1 | Two-layer access: what you may do (object) and which records (row) | Salesforce ★, Odoo record rules | CRM: `area.action` permissions plus role scope own / team / all (`scope.py`), and per-division promos and bundles. Inv, Ph: permissions only, no record scope. Plat: access grants. | open (proposed ADOPT: every app gets a record layer before it has records owned by teams) |
| B2 | One role drives both what you see and what you may do | SAP ★ | CRM, Inv, Ph: the sidebar and pages read the same permissions the API enforces. | open (proposed HAVE) |
| B3 | Field history people can query | SAP ★ (change documents), Salesforce (opt-in per field) | Every app: an audit log naming which fields changed, never their values (deliberate: safe to show admins). Inv, Ph: full stock movement ledgers. | open (proposed ADAPT: opt-in value history on chosen fields only, per Salesforce's cost lesson) |
| B4 | Lock a record after it's submitted | Veeva (pattern) | Ph: a verified prescription can't be changed; a recall is final. Inv: approved transfers are fixed. CRM: quote lines keep the price they were made at. No grace windows. | **ADOPT** (decided 2026-09-25, ICP: pharma first): P8 |

## C. Timeline and activity

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| C1 | One timeline any record can have (messages, activities, tracked fields) | Odoo ★ (`mail.thread`) | None. CRM activities link to a company or contact only. | open (proposed ADOPT: P1) |
| C2 | Typed scheduled activities (type, due, assignee, link, done) | Odoo ★ (`mail.activity`) | CRM partial: kind, due time, done, owner; linked to companies and contacts only. Others: none. | open (proposed ADAPT: CRM's activity on C1's polymorphic link) |
| C3 | Feed with posts, @mentions and followers | Salesforce ★ (Chatter) | None. Plat has ticket and incident notes. | open |
| C4 | Structured interaction record (what was detailed, said, and how it landed) | Veeva (pattern) | **Built 2026-10-01:** a visit records the products discussed in order, each with its key message and the doctor's reaction, and the next visit's objective; Field work sums a month's detailing. Samples given wait for sample management. | **ADOPT** (decided 2026-09-25, ICP: pharma first): P6 |
| C5 | Call plans with attainment | Veeva (pattern) | CRM partial: monthly field goals and a performance screen; no per-account visit frequency. | **ADOPT** (decided 2026-09-25, ICP: pharma first): P7 |

## E. Views and reporting

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| E1 | One list as table, board or chart | Odoo ★, Salesforce (table/kanban) | None: lists are tables; charts only on fixed screens (CRM retention and trends, report pages). | open (proposed ADOPT: P2, the "table, board and chart" rule) |
| E2 | Filters stored as data | Odoo ★ (domains) | None: filters live in the URL, not saved. | open (proposed ADOPT with E1) |
| E3 | Report types: pre-approved joins users filter without SQL | Salesforce ★ | Inv: about 15 dated reports with per-warehouse filters and CSV. Ph: six date-ranged reports. CRM: people and retention reports (CSV). Plat: dashboards. | open (proposed ADAPT: Inventory's report registry as the pattern) |
| E4 | Documents (PDF) from the same data the screens use | Odoo ★ (QWeb) | None. CRM only accepts uploaded PDFs (guarantee letters). | open |
| E5 | Receivables outstanding and ageing as a main screen | Marg ★ | **Finance: Invoices → Receivables** (`routers/receivables.py`): what each customer owes on issued invoices, not yet due and 1-30, 31-60, 61-90, over 90 days late; sales invoices numbered from the BIR's ATP series, VAT from the engine, posted to receivables, sales and output VAT; payments posted against them. CRM partial: what a doctor owes now (field collections). | **ADOPT** (decided 2026-09-25, D4): a main screen in the Finance app, with invoices and payments |

## F. Selling and pricing

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| F1 | Pipeline stage separate from forecast category | Salesforce ★ | **Built 2026-10-01:** deals on customers; each stage gives a probability and a forecast category, which the deal then keeps as its own. Pipeline board and forecast by person (CRM → Deals). | **ADOPTED** (decided 2026-09-25, D2) |
| F2 | Lead conversion in one transaction | Salesforce ★ | None: a lead is a company status, not its own record. | **SKIP** (decided 2026-09-25, D2): a lead stays a company status; there's no separate Lead record to convert |
| F3 | Guided path: a checklist per stage on the record | Salesforce ★ | Ph partial: the 10 prescription checks before verifying (fixed in code). Others: none. | open (proposed ADAPT: make checklists data, like Ph's) |
| F4 | Condition-based pricing: ordered, dated conditions | SAP ★ | CRM: an admin orders the price sources (customer-group price, team price, list price) and the adjustments (volume scale, promo, rep's discount, surcharge), switches each on or off, and adds dated rules; the most specific rule wins. Tax from Finance is the last step and is kept on the quote (Settings → Price rules). Inv, Ph: one price per item. | **ADOPT** (decided 2026-09-25, D4): ordered, dated conditions an admin sets; tax is the last step |
| F5 | Price lists per customer or customer group | Marg ★ | CRM: price groups (a customer is in one), with group prices per product, optionally per price type; still per team and per price type too. Inv: buying prices per supplier. | **ADOPT** (decided 2026-09-25, D4): per customer group, as a condition in F4 |
| F6 | Trade schemes: buy X get Y, slabs, validity windows | Marg ★ | CRM: promos (percent, amount, buy X get Y, tiered), dated, per division; bundles. | open (proposed HAVE) |
| F7 | Approvals by discount depth or value | SAP | CRM: quotes over the discount limit, or at a price type that needs it, wait for approval. Inv: adjustments wait for an approver (not by value). | open (proposed HAVE) |
| F8 | Tax engine: rules, groups, inclusive/exclusive | Odoo ★ | **Finance: the engine** (`app/tax/engine.py`): country packs, dated rates in `nbfi_tax_rates`, prices with or without tax, buyer treatments, the company's registration; asked by other apps at `/integration/tax`: the CRM asks it for every quote when its price rules add tax. Inv partial: a tax rate and inclusive flag per product. | **ADOPT** (decided 2026-09-25, D4, D8): one engine, a tax set per country; each company picks its country |
| F9 | Country tax rules | Marg ★ (GST) | **Finance: the Philippines pack** (`app/tax/packs/ph.py`): VAT 12%, zero-rated, VAT-exempt, senior citizen and PWD 20% with VAT exemption, percentage tax for non-VAT sellers with its dated history, and the Sales Invoice summary. No other country yet. | **ADAPT** (decided 2026-09-25, D8): country packs on F8's engine. **The Philippines first** (VAT, BIR invoices); others like India's GST, e-invoicing and e-way bills when a company there needs them |

## G. Stock and the field

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| G1 | Batch, expiry and FEFO | Marg ★ | Inv: batches, expiry, serials, FEFO picking. Ph: batches, expiry, FEFO dispensing and sales; expired, quarantined or recalled lots can't be given out. Two separate implementations. | **HAVE** (decided 2026-09-25, ICP: pharma first); one shared stock model is still a separate question |
| G2 | Keyboard-first grid entry | Marg ★ | None beyond the kit's list selection keys. | open (proposed ADOPT: P4, on high-volume entry screens first) |
| G3 | Offline with sync and conflict handling | Veeva ★ (by design), Marg (desktop) | None. | **ADAPT** (decided 2026-09-25, D7): visits and collections only, queued on the phone, clashes flagged; not full offline |
| G4 | Route and van selling, field visits | Marg ★ | CRM: field visits with GPS, clinic pins, agents' trails and day routes. No offline route orders. | **ADAPT** (decided 2026-09-25, D7): visits and collections work offline (G3); van and route orders are out for now |
| G5 | Effective-dated assignments ("who owned this in March") | SAP ★ | None: a record keeps its owner's team as a snapshot, undated. | open (proposed ADOPT for team membership and ownership) |
| G6 | Territory management | SAP | None. | SKIP (reference only, per best-of-breed.md: heavy) |

## H. Platform

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| H1 | Automated actions (on create, change, delete, or time) | Odoo ★ | None. | open |
| H2 | Portal users: outsiders see their own records | Odoo ★ | None. Plat serves public notices without sign-in. | open |
