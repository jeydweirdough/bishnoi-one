# Naming plan: Bishnoi One and its apps

Proposed 2026-10-26, for decision. Modelled on Zoho One: one suite, apps named for the one job each
does (Zoho CRM, Books, Inventory, Analytics, People), then the same words, at the same level, in
every app. Nothing is renamed until the open decisions at the end are made.

## 1. The levels, and how each is named

| Level | What it is | How it's named | Example |
|---|---|---|---|
| Suite | Everything a company signs in to once | **Bishnoi One** | Bishnoi One |
| App | One job, its own API and database | **Bishnoi + one noun** for the job | Bishnoi CRM, Bishnoi Books |
| Area | A group in an app's sidebar | Zoho's standard words, by the work | Sales, Purchases, Accountant |
| Page | A list or screen in an area | Plural record name, sentence case | Sales orders, Purchase receives |
| Record | One thing on a page | Singular, with its number | Invoice INV-40000123 |
| Action | A button | Verb + object, sentence case | New invoice, Record payment |
| Setting | A set-up list | Plural noun, under Settings | Warehouses, Price types |

Rules that hold at every level: sentence case, no "&", no internal codes on screen, one word per
thing across all apps (a supplier is a **Vendor** everywhere, an activity history is the
**Activity log** everywhere), and no two apps with the same name for different things.

## 2. The apps (proposed display names)

The keys (`crm`, `finance`, …), table prefixes and API ports stay as they are; only what people
see changes. Addresses (`/finance`) can follow at cutover, with the old ones forwarding.

| Today | Proposed name | Its job, in one line | Zoho counterpart |
|---|---|---|---|
| CRM | **Bishnoi CRM** | Customers, deals, quotes, field sales, retention | Zoho CRM |
| Finance | **Bishnoi Books** | Invoices, receivables, expenses, ledger, BIR | Zoho Books |
| Inventory | **Bishnoi Inventory** | Items, stock, sales and purchase orders, CPR | Zoho Inventory |
| Pharmacy | **Bishnoi Pharmacy** | Prescriptions, dispensing, counter sales | (Zoho has none) |
| Executive Admin | **Bishnoi Office** *(open)* | Permits, documents, leases, fleet, travel, office requests | Zoho Facilities-style |
| Regulatory *(soon)* | **Bishnoi Regulatory** | FDA registrations, licences, renewals | — |
| In-Licensing *(soon)* | **Bishnoi Licensing** *(open)* | Products licensed in from partners | — |
| Admin Console | **Bishnoi One Admin** | Companies, apps, People, Roles (the directory) | Zoho One Admin Panel |
| Each app's Reports | **Reports** now; **Bishnoi Analytics** later | One app's reports now; across apps later | Zoho Analytics |
| *(future)* | Bishnoi People, Bishnoi Desk, Bishnoi Sign | HR, customer support, e-signatures | Zoho People, Desk, Sign |

Why rename Finance and Executive Admin:
- **Finance → Books.** "Finance" is a department, not a tool; Books is what it is (accounting and
  invoicing) and the word people know from Zoho Books. Its Expenses area keeps cash advances and
  liquidations until they grow into their own app (Bishnoi Expense).
- **Executive Admin → Office.** "Admin" clashes with administration (Users and roles, the Admin
  Console) in every app; its job is running the office and its compliance.

## 3. The areas inside each app (sidebar groups)

Already in Zoho's words since 2026-10-24; kept, with three clashes fixed (marked ✱).

| App | Areas, in order |
|---|---|
| Bishnoi CRM | Sales (Leads, Customers, Contacts, Deals, Quotes, Order links, Retention) · Activities · Field sales · Products · Documents · Reports |
| Bishnoi Books | Sales (Invoices, Receivables) · Expenses · Approvals · Banking · Accountant · Taxes · Calendar · Reports |
| Bishnoi Inventory | Items · Inventory · Sales (Sales orders, Reservations) · Purchases · Reports |
| Bishnoi Pharmacy | Dispensing (Prescriptions, Dispensing, **Counter sales** ✱) · Customers · Inventory · Approvals · Reports |
| Bishnoi Office | Compliance · Fleet and travel · Office requests · Marketing · Reports |
| Every app, at the foot | Users and roles (Users, Roles) · Settings (… , Activity log) |

✱ Clashes fixed: Pharmacy's "Sales" becomes **Counter sales** (it is the counter, not the sales
team); Pharmacy's "Suppliers" becomes **Vendors** (Inventory's word); the CRM's "Products" area
keeps its name but its pages say where items come from (Bishnoi Inventory).

## 4. The organisation's words (one meaning each)

| Word | Means | Not to be used for |
|---|---|---|
| **Company** | A customer of Bishnoi One (GetMeds), its own databases | A customer of the company |
| **Division** | A business line in the org chart: Rx (STC, URO, B&B), HOS, B2B, B2C, Government | — |
| **Team** | People working together inside a division (HOS NCR 1, B2B CRR) | — |
| **Department** *(open)* | Today used for a division's settings ("Department settings") | Decide: replace with Division, or keep for functions (Sales, Finance, HR) |
| **Role** | What a person may do (Administrator, Manager, Team lead, Salesperson, Field agent) | A job title |
| **Title** | A person's job title (Pharmacist, Medical representative) | Permissions |
| **Customer** | A company or person the company sells to (hospital, drugstore, doctor, patient) | A Bishnoi One company |
| **Vendor** | Someone the company buys from | — |

## 5. Decisions needed

1. **Finance → Bishnoi Books?** (recommended)
2. **Executive Admin → Bishnoi Office?** (recommended; alternatives: Bishnoi Compliance, Bishnoi Admin)
3. **"Department"**: replace with **Division** everywhere (recommended), or keep it for functions?
4. **Admin Console → Bishnoi One Admin?** (recommended)
5. **In-Licensing → Bishnoi Licensing?**
6. **When**: display names now (screens, sidebar, module switcher, sign-in), addresses (`/finance` →
   `/books`) at cutover with forwarding (recommended).

## 6. Where names live (what changes once decided)

- `bishnoi-one-app/frontend/src/platform/lib/modules.ts`: each app's label and one-line blurb (module switcher, sidebar head, home page tiles).
- Each module's sidebar (`…/shell/nav.tsx`) for area and page names.
- Each API's `ORG`/app name settings and Platform > Applications names (sign-in, emails, passes).
- `CLAUDE.md`, `README.md`, the benchmarks and the Desktop status pages.
