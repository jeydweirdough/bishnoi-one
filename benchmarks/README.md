# Benchmarks

What every Bishnoi One app is measured against. Before a feature is designed, built
or reviewed, in any app, check it here.

Five products are the benchmarks, each for what it does best. Bishnoi One is built
for **pharma distribution** first (decided 2026-09-25), which is why Veeva is
one of them:

| Benchmark | What we take it as the reference for |
|---|---|
| **Salesforce** | The metadata platform: custom fields, layouts, sharing, validation, reporting |
| **SAP** | Master data and pricing: one party with roles, condition-based pricing, dated org structures |
| **Odoo** | The closest match to how we're built: one timeline for any record, one filter shown as table, board or chart |
| **Marg ERP** | Indian pharma distribution: keyboard entry, batches and expiry, trade schemes, GST, receivables |
| **Veeva** | Pharma field work: structured doctor visits, call plans, offline, records locked once submitted. Its regulated extras stay out (see best-of-breed.md) |

## The files

| File | What it's for |
|---|---|
| [benchmark-matrix.md](benchmark-matrix.md) | **The benchmark.** One row per capability: who does it best, where each of our apps stands today, and the decision for it |
| [best-of-breed.md](best-of-breed.md) | Reference notes: what each benchmark actually does, and why it matters to us |
| [patterns-to-adopt.md](patterns-to-adopt.md) | Patterns we build every app to, whichever app it is |
| [decisions.md](decisions.md) | The decisions rows depend on (ICP, D2, D4, D7, D8), what each means, and what's still open |

## The rules

1. **Nothing is ADOPT until its row has a decision** in the matrix. A note in
   best-of-breed.md is a reference, not a plan.
2. **A row's decision holds for every app.** If the CRM adopts custom fields
   the Salesforce way, the next app that needs custom fields does it the same
   way, from the same kit, rather than inventing its own.
3. **Say where we are, not where we'd like to be.** The "Ours today" column
   records what the code does now, app by app, and is updated when that
   changes.
4. **One reference per row.** Each row names the one benchmark that is the
   reference for it. We match that one; we don't average all four.
5. **Out of scope stays out.** What best-of-breed.md lists as not
   transferable isn't built. AI features are out, by the project's rules.

## Decisions

Each row's **Decision** is one of:

| Decision | Means |
|---|---|
| **ADOPT** | Build it the benchmark's way |
| **ADAPT** | Build our version of it; the row says what differs and why |
| **HAVE** | We already do it well enough; keep it that way |
| **SKIP** | Not for us; the row says why |
| **open** | Not decided yet. A *proposed* decision may be noted beside it, but it isn't a decision until someone who owns the product makes it |

## Using it

**Before you build a feature:** find its row. If it's `open`, get the
decision first. If it's ADOPT or ADAPT, build to the reference and to
patterns-to-adopt.md.

**When you finish one:** update "Ours today" for your app in the same pull
request.

**When you review a pull request or a new app:** check the features it adds
against their rows (MAINTAINING.md, "Reviewing a new app").

**A capability with no row:** add the row, with its reference and "Ours
today", and leave the decision `open`.
