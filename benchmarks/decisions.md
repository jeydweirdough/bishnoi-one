# Decisions

The decisions the benchmark rows depend on. Each was open until the people who
own the product decided it. When one changes, record it here with the date,
then update the rows it settles in [benchmark-matrix.md](benchmark-matrix.md).

D1, D3, D5 and D6 weren't described in the original brief. Add them here when
they're known.

## Decided on 2026-09-25

| ID | The question | Decided | What it means |
|---|---|---|---|
| ICP | Who do we mainly build for? | **A: pharma distribution** | Veeva becomes a full benchmark alongside Salesforce, SAP, Odoo and Marg. Pharma field work comes first: structured doctor visits, call plans, batches and expiry, locked records. Veeva's regulated extras stay out (samples, e-signatures, Sunshine Act, MLR review, AI). |
| D8 | Which country and tax regime? | **C: several countries** | A tax engine with a tax set per country (Odoo's fiscal positions); each company picks its country. Country rules are packs on that engine. **The Philippines pack comes first** (VAT and BIR invoices); others, like India's GST, e-invoicing and e-way bills, come when a company there needs them. |
| D4 | How far do pricing, quotes and invoices go? | **C: pricing rules + invoices** | Pricing becomes ordered, dated conditions an admin sets (SAP's condition technique): base, customer-group price, volume scale, promo, surcharge, tax. Sales run quote → order → invoice with tax, then payments and a receivables ageing screen. **Sales orders live in Bishnoi One Orders**, a separate system outside this repo: quotes (CRM) hand over to it, and invoices, payments and ageing belong to the Finance app. |
| D2 | Where does a lead live, and can we see expected sales? | **B: add deals to customers** | A lead stays a company status (prospect). Customers get **deals**, each with a stage, an expected value and a forecast category kept apart from the stage (Salesforce's pipeline idea). A won deal leads to a quote. There's no separate Lead record and no lead conversion. |
| D7 | Do field agents need to work without signal? | **B: offline visits and collections** | Logging a visit and recording a collection work offline on the phone, wait there, and sync when there's signal, with clashes flagged. Everything else still needs a connection. Full offline (Veeva-style) and van/route orders are out for now. |

## What has to come first, and where it stands

The decisions depend on each other, so the build follows this order:

| Step | Why it's in this place | Status |
|---|---|---|
| 1. **The tax engine (D8), with the Philippines pack** | An invoice can't be made without the tax rules for its country | **Done** 2026-09-25: Finance → **Tax** (matrix F8, F9) |
| 2. **Pricing conditions (D4)** | The tax step is the last condition in the price | **Done** 2026-09-25: CRM → Settings → **Price rules**, tax from Finance (matrix F4, F5) |
| 3. **Invoices, payments and ageing (D4)**, in the Finance app | Needs steps 1 and 2 | **Done** 2026-09-30: Finance → **Invoices** (sales invoices, payments, receivables; matrix E5) |
| 4. **Deals (D2)** and **offline visits and collections (D7)** | Stand on their own | Deals **done** 2026-10-01: CRM → **Deals** (pipeline board, forecast; matrix F1), with monthly **revenue targets** and **Results** (won against target by person, team, customer and product). Offline (D7) not started (matrix G3, G4) |

## Follow-ups, decided on 2026-09-25

| Question | Decided |
|---|---|
| Which country pack comes first (D8)? | **The Philippines** (VAT, BIR invoices). Others follow when a company in that country needs them. |
| Where do sales orders live (D4)? | **In Bishnoi One Orders**, the user's separate sales-order system, outside this repo and not benchmarked here. This repo covers quotes before it (CRM) and invoices, payments and ageing after it (Finance). |

## Open-source for lead generation, reviewed on 2026-10-01

From the "100 GitHub Repos for Lead Generation" list. Small libraries go in the apps; for anything heavy or needing a server, the idea is taken and built in our own code; whole products stay outside.

| Use | Where |
|---|---|
| `phonenumbers` (Google's libphonenumber) | **In use** in the CRM since 2026-10-01: numbers are matched however they're written, for duplicate warnings. Read as local to the company's country (from its locale); several countries (D8) will need the country per customer. |
| `email-validator` | **In use** in the CRM since 2026-10-01 for every email address. The domain isn't checked for mail, so it works without the internet. |
| splink's idea (block, then score) | **Built** 2026-10-01 in our own code, no library: Customers → Possible duplicates, and merge. A merged id still leads to the record kept (`nbcm_merged_records`), for Finance and old links. |
| fullcalendar's idea | **Built** 2026-10-01 in our own code: Activities → Calendar, a month grid. Planned visits join it with call plans (P7). |
| mjml's idea | **Built** 2026-10-01 in our own code (app/mail.py): one table layout with inline styles, plus a text version. Quote approvals are emailed through an email delivery service's SMTP (EMAIL_ENABLED, EMAIL_MODE). |
| photon | **Not needed:** a customer's map point comes from the rep's GPS at the clinic (Field work), more exact than an address lookup, and no geocoder to host. |
| OpenRefine | For staff, outside the app: cleaning a spreadsheet before importing it. |

Not used: Google Maps, LinkedIn and review scrapers, OSINT tools, and anything for getting around site blocking (against the sites' terms, and building profiles of doctors without consent runs against the Data Privacy Act); WhatsApp Web automation (against WhatsApp's terms; use the official Business API); whole CRMs and ERPs under GPL or AGPL (looking at them for ideas is fine, copying their code into a licensed product isn't); self-hosted mail servers.

## KPI management, decided on 2026-10-02

The fixed field goals (four measures) and revenue targets became **KPIs an administrator defines** (Settings → KPIs), with monthly targets per person and per team and a scorecard. A KPI counts one of the measures the CRM knows (app/kpis.py), perhaps narrowed, or is entered by hand; a formula language was not built (safer, and enough for now). The five old goals are built-in KPIs that keep what they measure; their saved targets moved over (migration 0031).

New goal, same day: **lead sources and integrations** (checklist g-lead-sources, g-integrations): leads from LinkedIn, Facebook and Google lead forms and AI research through official APIs only, and webhooks, a public API, an MCP server and connectors, with every app and AI call logged. Not started; the first sources are the user's to pick.

## Ant Design for the CRM's screens, decided on 2026-10-02

The CRM's screens use **Ant Design 6** (antd), set in **Poppins** (the font it already had). The theme is set once (`src/platform/app/ant-theme.tsx`: Ant's blue `#1677ff`, radius 6, the registry for server rendering). The shared pieces became Ant's: buttons and link buttons (`ui/ant-button.tsx`), text inputs, text areas and table-cell inputs, choices (radio buttons), form errors (Alert), view switches (Segmented, still links), confirmations (Modal). The design tokens in `globals.css` carry Ant's palette, so what's drawn with Tailwind matches; every table gets Ant's header row. Kept native, drawn like Ant: dropdowns (their change events differ from antd's Select, used in dozens of forms) and toasts (sonner). Other apps keep their look until moved the same way.

## HubSpot as a benchmark, decided on 2026-10-03

**HubSpot** joins the benchmarks (best-of-breed.md), for how a CRM links its
records and lays out a record's page. Adopted from it: **associations with
labels** between any records, and one activity on several records (A10, C6,
P13); the **record page in three columns** (I1, P14); and **emails from each
rep's own connected mailbox** (C7): Gmail, Outlook, Zoho Mail, or any provider
by SMTP, set up in Settings → Connections. Order: associations, the record
page, email connections, then Veeva's approved emails. On the Desktop feature
benchmark page HubSpot has its own column, from our own review (it isn't in
the brief's lists).

## Several companies on one deployment, decided on 2026-10-05

No software license: a **company is registered on Bishnoi One Platform**
first, active and given the app, and only then can its people use it. One CRM
and one Inventory serve **five to ten companies**, and **each company has a
database of its own** (`neondb_getmeds`, `crm-getmeds.db`), rather than a
company column on every row or a schema each: nothing one company keeps can
reach another's screens, a company's data can be backed up or moved on its
own, and it works the same behind Neon's connection pooler. The sign-in page
asks for the company; a session belongs to one company. **A person can work
for two companies**: one Platform password, a standing (title, apps, role) at
each, and **Switch company** in the apps' menu. Today's data became GetMeds's.

## Promotional materials reviewed before use, decided on 2026-10-15

The ICP decision (2026-09-25) left Veeva's **MLR review** out. On 2026-10-15
the user asked for its core: promotional materials (leaflets, posters,
giveaways) are **approved by a pharmacist before they're produced**, and **a
department's manager approves each distribution**. Built across three apps,
linked through the Platform (Connections: Admin → Pharmacy, Admin → CRM):
the marketing assistant designs in **Admin** (role Marketing Assistant), the
pharmacist approves, returns with comments, or rejects each version in
**Pharmacy**, the executive office produces them into stock in Admin, and the
team's manager (or an administrator) approves each request in the **CRM**.
Still out: legal and medical reviewers beside the pharmacist, e-signatures,
and expiry dates on approved materials.
