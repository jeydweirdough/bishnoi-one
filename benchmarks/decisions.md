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
| D4 | How far do pricing, quotes and invoices go? | **C: pricing rules + invoices** | Pricing becomes ordered, dated conditions an admin sets (SAP's condition technique): base, customer-group price, volume scale, promo, surcharge, tax. Sales run quote → order → invoice with tax, then payments and a receivables ageing screen. **Sales orders live in Nabhi Orders**, a separate system outside this repo: quotes (CRM) hand over to it, and invoices, payments and ageing belong to the Finance app. |
| D2 | Where does a lead live, and can we see expected sales? | **B: add deals to customers** | A lead stays a company status (prospect). Customers get **deals**, each with a stage, an expected value and a forecast category kept apart from the stage (Salesforce's pipeline idea). A won deal leads to a quote. There's no separate Lead record and no lead conversion. |
| D7 | Do field agents need to work without signal? | **B: offline visits and collections** | Logging a visit and recording a collection work offline on the phone, wait there, and sync when there's signal, with clashes flagged. Everything else still needs a connection. Full offline (Veeva-style) and van/route orders are out for now. |

## What has to come first

The decisions depend on each other, so the build follows this order:

1. **The tax engine (D8), with the Philippines pack**, comes before
   invoices: an invoice can't be made without the tax rules for its country.
2. **Pricing conditions (D4)** come before invoices too: the tax step is the
   last condition in the price.
3. **Invoices, payments and ageing (D4)** then go into the Finance app, which
   has only sign-in today.
4. **Deals (D2)** and **offline visits (D7)** stand on their own, and can be
   built alongside the rest.

## Follow-ups, decided on 2026-09-25

| Question | Decided |
|---|---|
| Which country pack comes first (D8)? | **The Philippines** (VAT, BIR invoices). Others follow when a company in that country needs them. |
| Where do sales orders live (D4)? | **In Nabhi Orders**, the user's separate sales-order system, outside this repo and not benchmarked here. This repo covers quotes before it (CRM) and invoices, payments and ageing after it (Finance). |
