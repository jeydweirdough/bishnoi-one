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
| A4 | Import (CSV/XLSX) and bulk actions | Salesforce | CRM: import wizard (`routers/imports.py`) and bulk jobs (`routers/bulk.py`). Inv, Ph, Plat: bulk-selection UI in the kit, no import or bulk routes. Fin: chart of accounts from a CSV (Oojeema's or Zoho's), read in the browser, each row checked first, added all or none (`routers/ledger.py`). | open (proposed ADAPT: CRM's import and bulk into the shared kit) |
| A5 | Duplicate and matching rules (what's a match, separate from warn or block) | Salesforce ★ | CRM: warns on save and allows an override (companies, contacts); fixed matching, no warn/block setting. Others: none. | open (proposed ADAPT: split matching from the action) |
| A6 | Custom fields as data, with no migration | Salesforce ★ | CRM: admin-made fields and sections (Settings → Forms, `extra` JSON on companies, contacts, products, quotes). Inv partial: free `attributes` JSON. Ph, Plat: none. | open (proposed ADAPT: CRM's forms become the kit's, for every app) |
| A7 | Layouts and required fields per record type | Salesforce ★ | CRM partial: one layout per entity, required/hidden per field, not per customer type. Others: none. | open |
| A8 | Declarative validation rules, errors on the named field | Salesforce ★ | Every app: rules in code (pydantic); errors already come back on the named field. CRM partial: admin-set required fields and options. | open (proposed ADAPT: keep code rules, add admin rules on custom fields) |
| A9 | Extend a record without forking its code | Odoo ★ | None: each app is its own codebase. | open (proposed SKIP: each app owns its code) |
| A10 | Associations with labels between any records, both ways | HubSpot ★ | CRM partial: contacts on a customer; since 2026-10-03 a customer field can point at another customer (a doctor's hospital), and the hospital lists who points at it. **Built 2026-10-03:** labelled associations between customers, contacts and deals, read both ways, with + Add on each record page (Settings → Associations keeps the labels). | **ADOPT** (decided 2026-10-03): P13 |

## B. Access and history

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| B1 | Two-layer access: what you may do (object) and which records (row) | Salesforce ★, Odoo record rules | CRM: `area.action` permissions plus role scope own / team / all (`scope.py`), and per-division promos and bundles. Inv, Ph: permissions only, no record scope. Plat: access grants. | open (proposed ADOPT: every app gets a record layer before it has records owned by teams) |
| B2 | One role drives both what you see and what you may do | SAP ★ | CRM, Inv, Ph: the sidebar and pages read the same permissions the API enforces. | open (proposed HAVE) |
| B3 | Field history people can query | SAP ★ (change documents), Salesforce (opt-in per field) | Every app: an audit log naming which fields changed, never their values (deliberate: safe to show admins). Inv, Ph: full stock movement ledgers. Fin: the tax registration shows its own history from that log (who, when, which parts) on the Tax page. | open (proposed ADAPT: opt-in value history on chosen fields only, per Salesforce's cost lesson) |
| B4 | Lock a record after it's submitted | Veeva (pattern) | Ph: a verified prescription can't be changed; a recall is final. Inv: approved transfers are fixed. CRM: quote lines keep the price they were made at. No grace windows. | **ADOPT** (decided 2026-09-25, ICP: pharma first): P8 |

## C. Timeline and activity

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| C1 | One timeline any record can have (messages, activities, tracked fields) | Odoo ★ (`mail.thread`) | None. CRM activities link to a company or contact only. | open (proposed ADOPT: P1) |
| C2 | Typed scheduled activities (type, due, assignee, link, done) | Odoo ★ (`mail.activity`) | CRM partial: kind, due time, done, owner; linked to companies and contacts only. Others: none. | open (proposed ADAPT: CRM's activity on C1's polymorphic link) |
| C3 | Feed with posts, @mentions and followers | Salesforce ★ (Chatter) | None. Plat has ticket and incident notes. | open |
| C4 | Structured interaction record (what was detailed, said, and how it landed) | Veeva (pattern) | **Built 2026-10-01:** a visit records the products discussed in order, each with its key message and the doctor's reaction, and the next visit's objective; Field work sums a month's detailing. Samples given wait for sample management. | **ADOPT** (decided 2026-09-25, ICP: pharma first): P6 |
| C5 | Call plans with attainment | Veeva (pattern) | **Built 2026-10-15:** each doctor has a tier (visits a month 4/2/1) and a zone (red, yellow, green); the weekly plan is filled from the zones (8 calls a day), submitted to the lead and reviewed; coverage of the list against 80% and each tier on plan, on the agent's Home and the Doctors list. | **ADOPT** (decided 2026-09-25, ICP: pharma first): P7 |
| C6 | One activity on several records (the doctor and the hospital) | HubSpot ★ | **Built 2026-10-03:** "Also about" puts an activity on more customers; it shows on each. | **ADOPT** (decided 2026-10-03): P13 |
| C7 | Emails sent from each rep's own connected mailbox, kept on the record | HubSpot ★ | **Built 2026-10-03:** Gmail, Outlook, Zoho Mail by each person's sign-in, or SMTP (app/mailbox.py); approved emails from Settings → Approved emails. | **ADOPT** (decided 2026-10-03) |
| C8 | Inbound channels in one inbox (lead forms, website chat, messaging) | HubSpot ★ (conversations inbox, lead ads) | **Built 2026-10-19 (CRM):** the Lead inbox (Customers → Lead inbox, `routers/inbox.py`, nbcm_inbox_leads): Facebook lead forms and Messenger, WhatsApp Business (Cloud API), Viber, Tawk.to chats and tickets, and the website's own forms or Make/Zapier call `/hooks/<channel>?company=<slug>`, each signed with the secret kept on Platform (Companies → Connections); unsigned calls are refused. More messages from one sender join their lead; someone with customers.inbox adds it as a new customer (or to the one the duplicate check finds), which keeps the conversation as a note and a task to reply within 4 hours, or dismisses it. Replying from the CRM: not yet. | **ADOPT** in part (decided 2026-10-19) |

## E. Views and reporting

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| E1 | One list as table, board or chart | Odoo ★, Salesforce (table/kanban) | **Built 2026-10-19 (CRM), after Twenty:** Customers and Quotes have Table | Board (`?layout=board`); customers by type, a card dragged to another column takes that type (customers.edit); quotes by where they stand (waiting, ready, ordered, rejected), read-only. Deals already had its board. Charts per list: not yet. | **ADOPT** (decided 2026-10-19) |
| E2 | Filters stored as data | Odoo ★ (domains) | **Built 2026-10-19 (CRM), after Twenty:** saved views on Customers, Contacts, Deals, Quotes and Activities (`routers/views.py`, nbcm_saved_views): the list's address (filters, search, sort, layout) kept by name; private, or shared with everyone by a role wider than own; only the owner (or an administrator) changes one. | **ADOPT** (decided 2026-10-19) |
| E3 | Report types: pre-approved joins users filter without SQL | Salesforce ★ | Inv: about 15 dated reports with per-warehouse filters and CSV. Ph: six date-ranged reports. CRM: people and retention reports (CSV). Plat: dashboards. | open (proposed ADAPT: Inventory's report registry as the pattern) |
| E4 | Documents (PDF) from the same data the screens use | Odoo ★ (QWeb) | None. CRM only accepts uploaded PDFs (guarantee letters). | open |
| E5 | Receivables outstanding and ageing as a main screen | Marg ★ | **Finance: Invoices → Receivables** (`routers/receivables.py`): what each customer owes on issued invoices, not yet due and 1-30, 31-60, 61-90, over 90 days late; sales invoices numbered from the BIR's ATP series, VAT from the engine, posted to receivables, sales and output VAT; payments posted against them. CRM partial: what a doctor owes now (field collections). | **ADOPT** (decided 2026-09-25, D4): a main screen in the Finance app, with invoices and payments |
| E6 | Customer credit standing, value tier and products carried, worked out | SAP credit management; Marg ★ | **Built 2026-10-19 (CRM + Finance):** a B2B customer's Trade profile (`app/trade.py`): credit status from Finance's unpaid invoices (good standing, approaching due within 5 days, overdue, suspended over 90 days late; Finance `/integration/customers`), checked on every B2B quote for Finance to confirm or put on hold (a hold stops the order; Quotes → Credit to confirm; permission orders.credit); products they carry from orders, deals won and invoice lines; Priority / High priority from the last 12 months' GetMeds billings (won deals while Finance can't be asked) plus 2MG sales, top 20% High priority, next 30% Priority. Which customers: the teams the Credit terms field is on (B2B NBD and B2B CRR). | **ADAPT** (decided 2026-10-19, B2B requirements) |

## F. Selling and pricing

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| F1 | Pipeline stage separate from forecast category | Salesforce ★ | **Built 2026-10-01:** deals on customers; each stage gives a probability and a forecast category, which the deal then keeps as its own. Pipeline board and forecast by person (CRM → Deals). | **ADOPTED** (decided 2026-09-25, D2) |
| F2 | Lead conversion in one transaction | Salesforce ★ | None: a lead is a company status, not its own record. | **SKIP** (decided 2026-09-25, D2): a lead stays a company status; there's no separate Lead record to convert |
| F3 | Guided path: a checklist per stage on the record | Salesforce ★ | Ph partial: the 10 prescription checks before verifying (fixed in code). Others: none. | open (proposed ADAPT: make checklists data, like Ph's) |
| F4 | Condition-based pricing: ordered, dated conditions | SAP ★ | CRM: an admin orders the price sources (customer-group price, team price, list price) and the adjustments (volume scale, promo, rep's discount, surcharge), switches each on or off, and adds dated rules; the most specific rule wins. Tax from Finance is the last step and is kept on the quote (Settings → Price rules). Inv, Ph: one price per item. | **ADOPT** (decided 2026-09-25, D4): ordered, dated conditions an admin sets; tax is the last step |
| F5 | Price lists per customer or customer group | Marg ★ | CRM: price groups (a customer is in one), with group prices per product, optionally per price type; still per team and per price type too. Inv: buying prices per supplier. | **ADOPT** (decided 2026-09-25, D4): per customer group, as a condition in F4 |
| F6 | Trade schemes: buy X get Y, slabs, validity windows | Marg ★ | CRM: promos (percent, amount, buy X get Y, tiered), dated, per division; bundles. | open (proposed HAVE) |
| F7 | Approvals by discount depth or value | SAP | CRM: quotes over the discount limit, or at a price type that needs it, wait for approval. Inv: adjustments wait for an approver (not by value). Fin: supplier bills wait for an approver (one told first, others backup), then a tax check only when tax is withheld, and are posted only when they clear (2026-10-23; not by value yet); manual journal entries wait for an approver. | open (proposed HAVE) |
| F8 | Tax engine: rules, groups, inclusive/exclusive | Odoo ★ | **Finance: the engine** (`app/tax/engine.py`): country packs, dated rates in `nbfi_tax_rates`, prices with or without tax, buyer treatments, the company's registration; asked by other apps at `/integration/tax`: the CRM asks it for every quote when its price rules add tax. Inv partial: a tax rate and inclusive flag per product. | **ADOPT** (decided 2026-09-25, D4, D8): one engine, a tax set per country; each company picks its country |
| F9 | Country tax rules | Marg ★ (GST) | **Finance: the Philippines pack** (`app/tax/packs/ph.py`): VAT 12%, zero-rated, VAT-exempt, senior citizen and PWD 20% with VAT exemption, percentage tax for non-VAT sellers with its dated history, and the Sales Invoice summary. **BIR reports** (`app/bir_reports.py`, 2026-10-24, from Oojeema): the books of accounts (sales, cash receipts, cash disbursements, general journal, general ledger), income statement and balance sheet, 2550Q/2551Q figures (sales side), the Summary List of Sales and the SAWT (tax customers withheld, recorded on payments from their 2307s), each as a screen and CSV; the RDO code and fiscal year on the tax profile. From the Finance team's **supplier bills** (`app/payables.py`: Finance's own supplier list with TIN, VAT status and usual ATC; input VAT and expanded withholding per line) the Purchase Journal, 2550Q input VAT, SLP, QAP, 0619E, 1601EQ, 2307 per supplier and 1604E. **Bank reconciliation** (`routers/bank.py`). The Sales DAT (`app/bir.py`, Prepare BIR files); the other DAT files once BIR's layout is confirmed. No other country yet. | **ADAPT** (decided 2026-09-25, D8): country packs on F8's engine. **The Philippines first** (VAT, BIR invoices); others like India's GST, e-invoicing and e-way bills when a company there needs them |
| F10 | Finding new leads (prospecting) | HubSpot (Breeze prospecting), Apollo | **Built 2026-10-19 (CRM):** Customers → Find leads with AI (`routers/lead_finder.py`): the CRM writes a prompt (where, kinds of customer, product focus, how many) and opens it in the person's own ChatGPT, Claude or DeepSeek; they paste the answer back, the CRM reads it (JSON or a table), flags missing details, types not on offer and look-alikes already in the CRM (other divisions' unnamed), and saves only the ticked ones as their customers with the source page and a call in two days. No company AI account needed. | **ADAPT** (decided 2026-10-19) |

## G. Stock and the field

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| G1 | Batch, expiry and FEFO | Marg ★ | Inv: batches, expiry, serials, FEFO picking. Ph: batches, expiry, FEFO dispensing and sales; expired, quarantined or recalled lots can't be given out. Two separate implementations. | **HAVE** (decided 2026-09-25, ICP: pharma first); one shared stock model is still a separate question |
| G2 | Keyboard-first grid entry | Marg ★ | **Built 2026-10-19 (CRM), after Twenty:** a command menu (Ctrl+K or /): one search across customers, contacts, deals, quotes and products (`routers/search.py`, each kind by the person's permissions and scope) and the pages and new-record actions their role allows, keyboard-driven. Grid entry: not yet. | **ADOPT** in part (decided 2026-10-19) |
| G3 | Offline with sync and conflict handling | Veeva ★ (by design), Marg (desktop) | None. | **ADAPT** (decided 2026-09-25, D7): visits and collections only, queued on the phone, clashes flagged; not full offline |
| G4 | Route and van selling, field visits | Marg ★ | CRM: field visits with GPS, clinic pins, agents' trails and day routes. No offline route orders. | **ADAPT** (decided 2026-09-25, D7): visits and collections work offline (G3); van and route orders are out for now |
| G5 | Effective-dated assignments ("who owned this in March") | SAP ★ | None: a record keeps its owner's team as a snapshot, undated. | open (proposed ADOPT for team membership and ownership) |
| G6 | Territory management | SAP | None. | SKIP (reference only, per best-of-breed.md: heavy) |
| G7 | Product registration (FDA CPR) | Marg ★ (drug licence fields) | **Built 2026-10-24 (Inventory):** each product's Certificate of Product Registration number and validity date (`app/cpr.py`, migration 0007), checked for the FDA's shape (DR-XY12345); every active stock product needs one. States: no CPR, no validity date, expired, expiring (within the expiry warning, 90 days), valid; filter on the product list, alerts (expired, expiring, incomplete), the report Product registrations (CPR), and Update CPR numbers: a CSV or pasted spreadsheet by SKU, checked line by line before saving. The CRM brings the CPR over with the product list and flags expired and expiring ones in its catalogue. Not blocked from sale yet. | **HAVE** (decided 2026-10-24, workstream 04): Inventory keeps it, the CRM shows it |

## H. Platform

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| H1 | Automated actions (on create, change, delete, or time) | Odoo ★ | None. | open |
| H2 | Portal users: outsiders see their own records | Odoo ★ | None. Plat serves public notices without sign-in. | open |

## I. Record pages

| ID | Capability | Reference | Ours today | Decision |
|---|---|---|---|---|
| I1 | A record's page in three columns: who and quick actions; overview and activities; associations | HubSpot ★ | **Built 2026-10-03** for customers. Contacts and deals have associations, not yet the three columns. | **ADOPT** (decided 2026-10-03): P14 |
