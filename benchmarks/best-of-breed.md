# Best-of-breed: what each benchmark does well

Reference notes only. Nothing here is ADOPT until it has a row decision in
[benchmark-matrix.md](benchmark-matrix.md). Veeva is the fifth benchmark,
since Bishnoi One is built for pharma distribution first; see the note at the end.
HubSpot is the sixth, added on 2026-10-03 for how a CRM links records and lays out a record's page.

## Salesforce: the metadata platform

| Feature | What it actually does | Why it matters here |
|---|---|---|
| Schema as data | Custom objects and fields are metadata rows, not DDL. No deploy to add a field. | Sets the ceiling for our custom fields row (A6). |
| Record Types + Page Layouts | One object, with a different layout, picklists and required fields per type, assigned by profile. | Cleanest answer to "one record, many views" for forms. |
| Forecast category ≠ stage | Stage sets a default probability; the forecast bucket (Pipeline / Best Case / Commit / Closed) is separately editable. | Best single idea in their pipeline model. Conflating the two kills forecasting. |
| List view ↔ kanban toggle | The same saved filter renders as a table or a board. | Directly serves our "table, board and chart" rule. |
| Report types | A saved, pre-approved join ("Accounts with Opportunities"). Users filter inside it, with no SQL. | How to make non-technical reporting safe. |
| Two-layer sharing | Object permissions (can you touch Opportunities) are separate from record sharing (which ones). | Our server-side authz needs a record-level model underneath. |
| Field History Tracking | Per-field opt-in audit, about 20 fields. Opt-in because logging everything is expensive. | Direct lesson for timeline cost. |
| Duplicate + matching rules | Fuzzy match on save; the matching logic is configured separately from the warn-or-block action. | Separating "what is a match" from "what we do about it" is the right split. |
| Validation rules | Declarative, on save; the error attaches to a named field. | Supports validate-at-entry. |
| Lead conversion | Lead → Account + Contact + Opportunity in one atomic transaction, with dedupe partway through. | The flow to copy if D2 keeps a separate Lead. |
| Path / guided selling | A per-stage checklist and coaching text on the record itself. | Stage definitions become usable instead of documented. |
| Chatter | Posts, @mentions, follow/unfollow and system events in one feed. | Timeline reference. |

## SAP (Sales Cloud / S/4HANA): master data and pricing

| Feature | What it actually does | Why it matters here |
|---|---|---|
| Business Partner with roles | One party record; Customer, Vendor and Employee are roles on it, not separate records. | Best master-data idea in the set. Avoids duplicate records for the same legal entity. |
| Condition technique | Price = an ordered sequence of condition records (base, customer discount, volume scale, surcharge, tax), each date-valid; an access sequence decides the winner. | The pricing reference if D4 pulls quoting in. Far better than a discount % field. |
| Effective-dated org structures | Territory and sales org assignments carry validity dates. | "Who owned this in March" is still answerable after a reassignment. |
| Territory management | Hierarchical, rule-based account assignment. | Reference only: heavy. |
| Conditional approvals | Routing depends on discount depth, value and margin. | Reference only. |
| Change documents | Field changes are queryable objects, not log lines. | Timeline design input. |
| Business roles | One object binds UI visibility and authorisation together. | Stops what-you-see and what-you-may-do drifting apart. |

## Odoo: closest architectural match, most directly copyable

| Feature | What it actually does | Why it matters here |
|---|---|---|
| `mail.thread` mixin | Any model inherits it and gets followers, messages, scheduled activities and tracked-field logging. | **Our polymorphic timeline rule, already solved. Read this one properly.** |
| View types over one action | One action and one domain render as list, kanban, calendar, pivot, graph or map, switched from the toolbar. | **Our "table, board and chart" rule, already solved.** Fuller than Salesforce's table/kanban. |
| Domain syntax | Filters are a serialisable expression stored as data, not code. | Why the same filter survives table → chart. Copy the shape if we invent our own. |
| `mail.activity` | A typed scheduled activity: type, due date, assignee, polymorphic link, completion state. | Activities ≠ notes ≠ calendar events. |
| Model inheritance | Extend a model with fields and overridden methods without forking. | Modularity. |
| Automated actions | Declarative create / write / unlink / time triggers → server actions. | Automation reference. |
| Tax engine | Per-jurisdiction rules, tax groups, inclusive/exclusive, fiscal positions swapping tax sets by country. | The invoicing reference if D4/D8 pull it in, not Salesforce. |
| Record rules | Row-level security as a domain per model per group. | Composable authz. |
| QWeb reports | Templated PDFs rendered from the same data the UI uses. | Document generation. |
| Portal users | External limited-access users see their own quotes and invoices. | Cheap external access without a seat. |

## Marg ERP: Indian distribution SMB; best at what the others ignore

| Feature | What it actually does | Why it matters here |
|---|---|---|
| Keyboard-first entry | The whole app works without a mouse: grid entry screens, deliberate tab order, consistent function keys. | An operator entering 200 lines an hour can't reach for a mouse. Marg is the benchmark for our keyboard-paths pattern, not Salesforce. |
| GST built in | GSTR-1 / 3B preparation, e-invoicing with IRN against the IRP, e-way bills. | If D8 lands on India, none of the other four give us this and we build it. |
| Batch / expiry / barcode | Stock tracked per batch with expiry; drives FEFO picking and expiry returns. | The pharma-distribution standard, absent from general CRMs. |
| Trade schemes / free goods | "Buy 10 get 1", slab discounts, validity windows: first-class objects, not manual line edits. | Scheme logic can't be retrofitted onto a discount field. |
| Per-party price lists | A different rate for the same item by customer or customer group. | Pricing model input. |
| Outstanding + ageing as a primary screen | Receivables ageing is a main screen, not a report you go and find. | Collection treated as core workflow. |
| Offline desktop + sync | A deliberate architecture for unreliable connectivity. | Input to D7. |
| Van sales / route selling | Route orders on mobile, synced later. | Input to D7. |

## Veeva: life sciences vertical

### Transferable (promoted to [patterns-to-adopt.md](patterns-to-adopt.md))

| Feature | What it actually does | Why it matters here |
|---|---|---|
| Structured interaction record | A "call" captures the products detailed, the order, the key messages delivered and the HCP's reaction, as required structured fields validated on submit. | **Strongest Veeva idea.** A note model can never report on *what was said*. |
| Call plans with attainment | The system holds "visit this account 8× this quarter" and tracks the variance. | Turns activity from a log into a plan. Nothing in the other four does this. |
| Offline-first full CRUD | Complete create / read / update offline, with sync reconciliation and conflict handling. | Best offline implementation in enterprise software; the reference if D7 goes field sales. Marg is offline by being on the desktop; Veeva is offline by design on a connected device. |
| Post-submission immutability | A submitted call locks after a grace window; regulated records can't be quietly edited. | Stronger than archive-never-delete: some records must not change at all after a point. |

### Not transferable: explicitly out of scope

Closed-loop marketing with slide-level engagement tracking; sample management
under 21 CFR Part 11 with e-signature and chain of custody; aggregate spend /
Sunshine Act transfer-of-value reporting; MLR content review in Vault; Network
externally curated HCP/HCO master data; Align territory design; Suggestions
(AI: out, per the project's rules).

## Veeva's status

At first Veeva was only a reference, for its four transferable ideas. On
2026-09-25 the ideal customer was decided as **pharma distribution** (ICP in
[decisions.md](decisions.md)), so Veeva is now a full benchmark: a matrix row
may name it as its reference, and pharma field work comes first. What's listed
above as not transferable stays out of scope.

## HubSpot: associations and the everyday CRM

Added as a benchmark on 2026-10-03 (decisions.md). Not in the brief's lists:
what it has is our own review of its hubs (sales, marketing, service, content,
operations, commerce).

### Transferable (promoted to [patterns-to-adopt.md](patterns-to-adopt.md))

| Feature | What it actually does | Why it matters here |
|---|---|---|
| Associations with labels | Any record links to any other (a contact to companies, deals, tickets), each link with a label an admin defines ("Decision maker", "Works at"), both ways. A company can be the parent of another. | **Strongest HubSpot idea.** A hospital's doctors, a hospital group's hospitals and a deal's decision maker are all one mechanism, not a column each. |
| Activities on several records | A note, email, call or meeting is logged once and associated with the contact, their company and the deal at the same time. | A visit note belongs on the doctor *and* the hospital; today it can sit on one customer. |
| The record page in three columns | Left: who it is and quick actions (Note, Email, Call, Task, Meeting) under the name, then "About". Middle: Overview and an Activities tab with search and filters. Right: associations, each with + Add. | Everything about one customer on one screen; the next action is always one click from the name. |
| Connected inboxes | Each rep connects their own Gmail or Outlook; emails sent from the CRM go out from their address and are logged on the record, with replies read back in. | Approved emails (Veeva) need a mailbox to send from; this is how. |
| Sequences | A series of emails and tasks to a contact, stopped when they reply or book a meeting. | Later: follow-up after a first visit. |

### Not transferable: out of scope for now

Marketing email at scale, landing pages, ads and social publishing (the
marketing hub); the service hub's tickets and customer portal; Breeze AI
(AI out, per the project's rules, until lead sources and integrations, g-integrations).


## Zoho (One, CRM, Books, Inventory): the suite and its sidebar

Added 2026-10-24 as the reference for how a suite of modules is navigated.
Zoho One gives one sign-in across its apps; each app's sidebar starts with an
app switcher and keeps its own menu short, grouped by the work (Zoho Books:
Sales, Purchases, Accountant, Reports). Blueprints draw a process as states,
with who may move a record on and what they must fill in. Settings are found
by search.

### Transferable (promoted to [patterns-to-adopt.md](patterns-to-adopt.md))

- The switcher at the top of the sidebar, listing only what you may use (P15).
- Menus grouped by process, not record type (P15).
- Blueprints as the track on a record, its approvals and the stuck report (P16).

### Not transferable

- Zoho's per-app separate settings and billing: ours stay on the Platform.
