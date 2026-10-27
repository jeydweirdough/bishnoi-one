# Bishnoi One CRM: implementation roadmap (RX Business and B2B)

**Company:** GetMeds Philippines · **Prepared:** 25 October 2026 · **Phase:** 1 (documentation only; no application code, data or schema was changed)
**Source of truth:** the business requirements of 25 October 2026 ("REA Benchmarking & Business Requirements"), checked against the repository at commit `0b2a686` plus the uncommitted sidebar and report-kit work.
**Companion:** [benchmark-analysis.md](benchmark-analysis.md) (the nine-product comparison and the evidence behind each item here).

Every task below names the code it changes, what it depends on, and how it is accepted. Items marked **Decision** cannot be built until the business owner answers the question in §1; nothing in this plan invents a rule.

---

## 1. Decisions needed before building (ambiguity register)

| ID | Question | What the code does today (evidence) | Why it matters | Proposed default, for approval |
|---|---|---|---|---|
| D-01 | **RX Field CHC cap of 70 on a 90-point card.** Is "capped at 70" 70 points (= 77.8%) or 70%? | The cap is applied to raw points, then the total is shown as a share of 90 (`app/scorecards.py` `score()`: `total = cap["total"]`, `percent = 100*total/out_of`). A capped RX month shows 77.8%, which lands in **Proficient (75)**. | A capped month currently earns a raise band the cap was meant to deny. | Cap at 70% of the card (63 of 90 points), so a capped month is Developing at most. |
| D-02 | **90-point denominator vs the 100-point convention.** | The RX card is out of 90 and shown as a percentage (`seed_scorecards.py` `rx_chc`; `score()` divides by `outOf`). | Bands are compared on the percentage, so 90 points = 100% = Distinguished. | Keep 90 and compare bands on the percentage (as today), recorded as the rule. |
| D-03 | **Rounding before banding.** | Rates (CRR, NZSD, coverage of a list) are rounded to a whole percent with Python's `round` (half to even: 70.5 → 70, 69.5 → 70) in `kpis.combine()`; attainment to one decimal (`scorecards.attainment()`), so 89.96% reads as 90.0 and crosses a 90% band. | Edge results decide points and caps. | Truncate (never round up across a threshold); keep one decimal for display only. |
| D-04 | **Missing results.** | A manual count KPI with no entry (HIT, cross-sell) scores **0** silently: `value_of(None, "count")` returns 0 (`kpis.py`). Finance measures without Finance show "No result yet" and 0 points but the month is still scored if any item has a result (`score()`: `scored = any(...)`). | A month can drop a band because data wasn't entered, not because of performance. | No entry = "No result yet", the item excluded from the denominator until the month is closed; at close, a missing entry scores 0 with an audit note. |
| D-05 | **Intermediate DSO thresholds** ("Up to 30 = 15; 40 = 11; 50 = 7; 60 = 3"). | Implemented as ranges: ≤30 → 15, 31–40 → 11, 41–50 → 7, 51–60 → 3, over 60 → 0 (`MDT_DSO`, `max` bands). | The requirement lists points at 40/50/60 only. | Confirm the ranges as implemented. |
| D-06 | **NZSD ₱500 minimum: per invoice or per day?** | Per invoice: a day counts when at least one invoice is ≥ ₱500 (`kpis._sale_days`, `totalCentavos >= minCentavos`). Two ₱300 invoices on one day don't count. | Changes B2B NZSD results. | Confirm per invoice, or change to the day's total. |
| D-07 | **NBD for B2B NBD.** The requirement's B2B NBD covers new customers, customers inactive 2–3 months and dormant customers (one order then ≥ 6 months none). | NBD counts only customers whose **first sale ever** is this month (`kpis._new_accounts` uses Finance's `firstSale`). Reactivations score nothing. | B2B NBD reps are under-credited for reactivations. | Count a customer as a new account when their previous invoice is ≥ 60 days before this month's first invoice (inactive) or they had exactly one prior order and none for ≥ 180 days (dormant). Exact day counts need approval. |
| D-08 | **CRR basis.** | Month over month: last month's customers (counted for last month's salesperson) who bought again this month (`kpis._customers_kept`). | A customer who buys every other month never counts as kept. | Confirm month-over-month, or move to a rolling window. |
| D-09 | **Credit confirmation before ordering.** "Finance must confirm credit or put the quote on hold." | Only a **hold** blocks ordering (`quotes.orderable()` → `on_hold()`); a quote Finance hasn't decided can be ordered. | The control can be bypassed by ordering before Finance looks. | Block ordering a B2B quote until Finance confirms (decision ≠ null); a hold also blocks. |
| D-10 | **Credit precedence.** | Suspended (> 90 days late) → Overdue (> 0) → Approaching due (Finance's 5-day flag) → Good standing (`trade.credit_of()`). | The requirement asks for it to be documented. | Approve as implemented. |
| D-11 | **TDC denominator.** | The scorecard uses a fixed 80 (`"of": 80` on the item) and counts **every** account visited (`kpis._doctors_visited`: distinct companies, any type). The Field page's coverage uses the agent's own doctor list (`routers/field.py` `COVERAGE_GOAL = 80`). | An agent with 60 doctors can never reach 80%; visits to hospitals or pharmacists inflate TDC. | Denominator = the agent's assigned doctor list (configurable per person), numerator = doctors of the visited type only. |
| D-12 | **HIT is scored quarterly.** | Entered and scored monthly like any manual KPI; no quarterly logic (`KpiEntry` is per month). | Points could be counted three times, or zero in two months of three. | Score HIT in the quarter's last month from the quarter's total; show "scored at quarter end" in the other months. |
| D-13 | **Bands on monthly vs yearly average.** | Bands are shown on the monthly percentage; the 12-month average isn't computed (documented as not yet scored). | Raises depend on the yearly average. | Build the 12-month average as its own figure (§3, P1-07); keep monthly bands labelled "guide". |
| D-14 | **PIP "if repeated".** | `band.pip` is true for Below standard in any month (`REP_BANDS`); no repeat logic. | The requirement says PIP if it repeats. | PIP flag only after 2 consecutive closed months below 60 (count to be approved). |
| D-15 | **Patient-assistance attachments.** IDs, application form, prescription, indigency certificate. | Attachments are typed only as `id` or `document` (`routers/assistance.py` upload `kind`); approval requires only the receipt number. | Evidence can't be checked per document type. | Typed attachment kinds; approval allowed without them (warning) unless the business makes any required. |
| D-16 | **Old invoices with no salesperson.** | They count for nobody (`/integration/sales` filters `salesperson_id IS NOT NULL` for owed; `_issued` matches salesperson). | History before the salesperson field is unattributed. | A one-off Finance backfill from the CRM owner at invoice date, reviewed before applying. |
| D-17 | **Owner changes.** | Finance stores the salesperson on the invoice when it's made (`nbfi_invoices.salesperson_id`); later CRM owner changes don't move past sales. | Matches "attributed to the salesperson on the invoice". | Approve as implemented (attribution frozen at invoicing). |
| D-18 | **Bonus points above 100% / 110%.** | Not scored (`seed_scorecards.py` docstring). | Playbooks don't give the points. | Wait for the rule. |
| D-19 | **NZSD holidays and leave.** | Monday to Saturday only (`Period.working_days()`). | Holidays lower everyone's NZSD. | Company holiday calendar (Finance already has `app/workdays.py` with Philippine holidays) plus approved leave per person. |
| D-20 | **BID and CLIDP.** The requirement says "CLIP". | The repo has CLIDP (FDA Certificate of Listing of Identical Drug Product, `app/clidp.py`) and a separate BID team. | Name check only; both stay separate from RX and B2B. | Confirm "CLIP" means CLIDP. |

---

## 2. What already exists (so it isn't rebuilt)

Verified in the repository; file references are the evidence.

| Requirement | Status | Evidence |
|---|---|---|
| A sale = Finance invoice issued (sent or paid) for the salesperson on it | Built | Finance `nbfi_invoices.salesperson_id` (migration 0012); statuses draft/issued/void, paid = issued with `paid_centavos` (`bishnoi-finance/backend/app/models.py`); feed `GET /integration/sales` (`routers/integration.py`); CRM `kpis._issued()` |
| Scorecards per team and role, bands, caps, team and team-average scopes | Built | `bishnoi-crm/backend/app/scorecards.py`, `app/tools/seed_scorecards.py` (12 cards, 26 KPIs) |
| RX Field CHC, MD Telesales CHC, B2B NBD/CRR CHC, B2B DSC exactly as specified | Built (seeded) | `CARDS` in `seed_scorecards.py` (`rx_chc`, `mdt_chc`, `b2b_nbd_chc`, `b2b_crr_chc`, `b2b_dsc`) |
| Ria worked example | Built (test) | `tests/test_scorecards.py::test_a_rep_is_scored_on_their_divisions_card` and `::test_a_missed_gate_caps_the_month...` |
| Manual monthly results, targets per person/team | Built | `routers/kpis.py` `/kpi-entries`, `/kpi-targets` (audited) |
| Scorecard screens (admin, rep, lead) and "no sales yet" list | Built | `GET /scorecards` (`noSales`), one app `app/(app)/crm/admin/settings/performance/scorecards/page.tsx` and `app/(app)/crm/performance/scorecards/page.tsx` |
| PAP from approved applications only, receipt required, month = approval day | Built | `routers/assistance.py`, `kpis._assistance_approved` |
| Tiers (4/2/1), zones (red/yellow/green → morning/midday/afternoon), 8 calls/day, Mon–Fri plan, coach review, 80% coverage goal | Built | `routers/field.py` (`TIER_VISITS`, `ZONES`, `COVERAGE_GOAL`), `routers/field_plan.py` (`CALLS_A_DAY = 8`, `WORK_DAYS = 5`) |
| Visit: products in order with key message and reaction, next objective, Patient Care Group, GPS and accuracy | Built | `models.Visit` (`detailing`, `next_objective`, `care_group`, `latitude`, `accuracy_m`) |
| RX customer types and fields; Industry, Lead source, Website, Country kept off | Built | `app/tools/rx_form.py` |
| B2B types (Distributor, Clinic, Drugstore), retired Drugstore chain and Wholesaler kept on old records | Built | `app/tools/split_b2b.py` (`is_active = False`, customers keep the type) |
| B2B fields: TIN, credit terms, potential, monthly volume, 2MG sales, landline, region | Built | `division_forms.py`, `split_b2b.py` |
| Credit status from Finance unpaid invoices; check on every B2B quote; hold blocks the order; queue "Credit to confirm" | Built (see D-09) | `app/trade.py`, `routers/quotes.py` (`credit_check`, `orderable`, `task=credit`, `POST /quotes/{id}/credit`) |
| Products carried, profile ranking (20% / 30% / rest) | Built | `app/trade.py` |
| B2B identified by the Credit terms field's teams | Built | `trade.trade_teams()` |
| Audit trail of changes (field names) | Built | every API's `audit()`; scorecard seed audits `scorecards.seeded` |

---

## 3. Phases

Each phase is shippable alone. Effort: S ≤ 2 days, M ≤ 1 week, L > 1 week (one developer). Dependencies name tasks or decisions.

### Phase 1: Scoring engine correctness and auditability (highest impact)

| Task | What | Code | Depends on | Effort |
|---|---|---|---|---|
| P1-01 | Rounding policy as a scorecard setting (truncate by default); rates and attainment banded on the unrounded value or truncated | `kpis.combine`, `scorecards.attainment`, `points_for` | D-03 | S |
| P1-02 | Missing results: "No result yet" items excluded from the total and denominator while the month is open; at close, missing = 0 with an audit note | `scorecards.score`, `kpis.value_of` | D-04 | M |
| P1-03 | Cap semantics on cards not out of 100 (`cap.total` read as a percentage of the card) | `scorecards.score`, `seed_scorecards` RX item caps | D-01, D-02 | S |
| P1-04 | **Month close and snapshots:** freeze each person's scored month (items, actuals, targets, points, cap, band, the card version and the Finance feed's totals) in a new `nbcm_scorecard_results` table; closed months are read from it, never recomputed; re-open needs a reason and is audited | new model and migration, `routers/kpis.py` | P1-02 | M |
| P1-05 | **Scorecard versions:** cards become effective-dated (`valid_from`); a change makes a new version; a closed month keeps the version it was scored on | `models.Scorecard`, seed tool | P1-04 | M |
| P1-06 | Quarterly KPIs (HIT): `period: quarter` on an item; scored in the quarter's last month from the quarter's entries | `scorecards.result`, `KpiEntry` reads | D-12 | S |
| P1-07 | 12-month average and raise band (separate from monthly bands), PIP after consecutive months | from snapshots | P1-04, D-13, D-14 | M |
| P1-08 | Scorecard editor screen (admins): items, weights, bands, caps, effective date; validation (weights add up to the card, bands descending) | `routers/kpis.py`, one app settings | P1-05 | L |

**Acceptance (Phase 1):** every band boundary in §5.1 passes; the Ria example passes unchanged; a closed month gives the same figures after Finance data changes; changing a card does not change a closed month; every change to a card, target, entry or a re-opened month appears in the audit log with who and when.

### Phase 2: Finance attribution and sales definitions

| Task | What | Code | Depends on | Effort |
|---|---|---|---|---|
| P2-01 | NBD reactivation (inactive and dormant customers) for B2B NBD: Finance's feed adds each customer's previous invoice date and order count; CRM counts per the approved rule | Finance `/integration/sales` (`lastSaleBefore`, `ordersBefore`), CRM `_new_accounts` with a filter `{"reactivated": true}` on the B2B NBD card only | D-07 | M |
| P2-02 | NZSD per-invoice vs per-day minimum as a KPI filter option | `_sale_days` | D-06 | S |
| P2-03 | Working days from the company calendar (Philippine holidays already in Finance `app/workdays.py`) plus approved leave per person | CRM `Period.working_days`, a leave record | D-19 | M |
| P2-04 | Backfill salesperson on old invoices from the CRM owner at invoice date: dry run, review list, apply, audit | Finance tool | D-16 | S |
| P2-05 | Feed resilience: the sales feed cached per month with its fetch time; scorecard shows "Finance data as of …"; a failed fetch keeps the last good copy for open months | `app/finance.py` `sales_feed` | — | S |
| P2-06 | Cross-sell accounts measured from Finance invoice lines (a product new to the customer in the last 6 months), replacing manual entry once approved | Finance feed lines, CRM measure `cross_sell` | business OK to automate | M |

**Acceptance (Phase 2):** a draft or void invoice never counts; an issued invoice counts for its salesperson even after the CRM owner changes; reactivated customers count for B2B NBD and not for first-sale-only cards; Finance unreachable shows "No result yet" (never 0) and the last good figures for an open month.

### Phase 3: Credit control

| Task | What | Code | Depends on | Effort |
|---|---|---|---|---|
| P3-01 | Block ordering a B2B quote until Finance confirms (decision present), not only on hold | `quotes.orderable` | D-09 | S |
| P3-02 | Re-check credit at order time; if the status worsened since confirmation (e.g. now Suspended), require a new decision | `quotes.orderable`, `trade.credit_check` | P3-01 | S |
| P3-03 | Credit queue service level: age of each waiting quote, reminder to `orders.credit` holders after N hours | `quotes` task=credit, notifications | — | S |
| P3-04 | Document precedence (D-10) on the credit panel ("Suspended: 104 days late on its oldest invoice") | one app quote page | D-10 | S |

**Acceptance (Phase 3):** see §5.4.

### Phase 4: RX field and patient assistance

| Task | What | Code | Depends on | Effort |
|---|---|---|---|---|
| P4-01 | TDC from the agent's assigned doctor list and the visited customer type only | `kpis._doctors_visited` filter `visitedType`; item `of: "list"` | D-11 | M |
| P4-02 | Typed attachments on assistance applications (ID, application form, prescription, indigency certificate, receipt); optional required set per agency | `routers/assistance.py` | D-15 | S |
| P4-03 | Follow-up flag after 7 days pending, on the agent's dashboard (pending actions live on dashboards) | assistance, CRM home | — | S |
| P4-04 | DOT measured from visits (Tier 1 doctors with 4 visits in the month ÷ Tier 1 doctors) instead of manual entry | new measure | business OK to automate | S |

### Phase 5: Reports (shared report kit, `src/platform/reports/`)

Scorecard history by person and team; band distribution by month; who has no sales; PAP pipeline (filed, pending > 7 days, approved, denied); coverage by tier and zone; credit queue ageing and holds; NBD (new vs reactivated); CRR cohort; DSO by customer. Each is a report in the CRM's registry (same contract as Inventory's) with drill-down to records. Effort M per group of three.

### Phase 6: Integrations

2MG sales read from 2MG's system when available (keeps the manual field until then); scheduled monthly close; Finance and CRM sync health on the Platform.

---

## 4. Migration, legacy and data rules

- **New tables:** `nbcm_scorecard_results` (P1-04) and scorecard versions (P1-05) are added in place, idempotent migrations, as the CRM's other migrations; nothing is rebuilt.
- **Legacy customer types:** Drugstore chain and Wholesaler stay `is_active = False`: shown on records that have them, never offered for new selections (as `split_b2b.py` does today). A report lists customers still on retired types for clean-up.
- **Missing data:** never a silent 0 (P1-02). Every item shows why it has no result: no target, no entry, Finance not linked, not scored this month (quarterly).
- **Manual results:** entered per person per month by `goals.manage`; after month close, changing one re-opens the month (reason required).
- **Configurable, not hard-coded:** thresholds, weights, caps, quotas, targets, coverage list sizes, credit day limits (5 and 90) and the profile shares (20%/30%) become settings or card data, not constants; today `SUSPENDED_DAYS`, `HIGH_SHARE`, `PRIORITY_SHARE`, `COVERAGE_GOAL`, `CALLS_A_DAY` and the TDC `of: 80` are constants or seed data.
- **Auditability:** card versions, targets, manual entries, month close and re-open, credit decisions (`quote.credit_confirm` / `quote.credit_hold` exist) and salesperson backfill all write the audit log (field names, never values, per the platform rule), plus the frozen snapshot holds the values for a closed month.

---

## 5. Tests

### 5.1 Band and threshold boundaries (from the configured cards)

Generated from `CARDS` in `app/tools/seed_scorecards.py`, so the expected points are what the engine is configured to give. "Just below" uses one decimal for attainment (rounded to 0.1 today) and one whole unit for counts and rates (rounded to whole percents today); D-03 may change the rounding, not the thresholds.


#### Rx field CHC (`rx_chc`), out of 90

| ID | KPI | Read as | x | Expected points | Case |
|---|---|---|---:|---:|---|
| rx_chc-01 | Assistance approved (PAP) | count | 11 | 25 | at threshold |
| rx_chc-02 | Assistance approved (PAP) | count | 10 | 23 | just below |
| rx_chc-03 | Assistance approved (PAP) | count | 8 | 23 | at threshold |
| rx_chc-04 | Assistance approved (PAP) | count | 7 | 20 | just below |
| rx_chc-05 | Assistance approved (PAP) | count | 5 | 20 | at threshold |
| rx_chc-06 | Assistance approved (PAP) | count | 4 | 15 | just below |
| rx_chc-07 | Assistance approved (PAP) | count | 3 | 15 | at threshold |
| rx_chc-08 | Assistance approved (PAP) | count | 2 | 10 | just below |
| rx_chc-09 | Assistance approved (PAP) | count | 1 | 10 | at threshold |
| rx_chc-10 | Assistance approved (PAP) | count | 0 | 0 | just below |
| rx_chc-11 | Formulary approvals (HIT) | count | 2 | 15 | at threshold |
| rx_chc-12 | Formulary approvals (HIT) | count | 1 | 10 | just below |
| rx_chc-13 | Formulary approvals (HIT) | count | 1 | 10 | at threshold |
| rx_chc-14 | Formulary approvals (HIT) | count | 0 | 0 | just below |
| rx_chc-15 | Product knowledge test (PKT) | percent (whole) | 80 | 10 | at threshold |
| rx_chc-16 | Product knowledge test (PKT) | percent (whole) | 79 | 0 | just below |
| rx_chc-17 | Gatekeeper set (gate) | points of the set | 30 | — | month total capped at 70 |
| rx_chc-18 | Brand detailing compliance (BDC) | percent (whole) | 90 | 10 | at threshold |
| rx_chc-19 | Brand detailing compliance (BDC) | percent (whole) | 89 | 0 | just below |
| rx_chc-20 | Joint field work score (JFW) | percent (whole) | 70 | 10 | at threshold |
| rx_chc-21 | Joint field work score (JFW) | percent (whole) | 69 | 0 | just below |
| rx_chc-22 | Total doctor coverage (TDC) | attainment % of 80 | 80 | 10 | at threshold |
| rx_chc-23 | Total doctor coverage (TDC) | attainment % of 80 | 79.9 | 0 | just below |
| rx_chc-24 | Total doctor coverage (TDC) (gate) | attainment % of 80 | 79.9 | — | month total capped at 70 |
| rx_chc-25 | Tier 1 doctors seen 4 times (DOT) | percent (whole) | 90 | 10 | at threshold |
| rx_chc-26 | Tier 1 doctors seen 4 times (DOT) | percent (whole) | 89 | 0 | just below |

#### MD Telesales CHC (`mdt_chc`), out of 100

| ID | KPI | Read as | x | Expected points | Case |
|---|---|---|---:|---:|---|
| mdt_chc-01 | Sales invoiced (IST) | attainment % | 91 | 40 | at threshold |
| mdt_chc-02 | Sales invoiced (IST) | attainment % | 90.9 | 32 | just below |
| mdt_chc-03 | Sales invoiced (IST) | attainment % | 81 | 32 | at threshold |
| mdt_chc-04 | Sales invoiced (IST) | attainment % | 80.9 | 24 | just below |
| mdt_chc-05 | Sales invoiced (IST) | attainment % | 71 | 24 | at threshold |
| mdt_chc-06 | Sales invoiced (IST) | attainment % | 70.9 | 16 | just below |
| mdt_chc-07 | Sales invoiced (IST) | attainment % | 60 | 16 | at threshold |
| mdt_chc-08 | Sales invoiced (IST) | attainment % | 59.9 | 0 | just below |
| mdt_chc-09 | Customers kept (CRR/HRR) | percent (whole) | 95 | 15 | at threshold |
| mdt_chc-10 | Customers kept (CRR/HRR) | percent (whole) | 94 | 13 | just below |
| mdt_chc-11 | Customers kept (CRR/HRR) | percent (whole) | 85 | 13 | at threshold |
| mdt_chc-12 | Customers kept (CRR/HRR) | percent (whole) | 84 | 11 | just below |
| mdt_chc-13 | Customers kept (CRR/HRR) | percent (whole) | 75 | 11 | at threshold |
| mdt_chc-14 | Customers kept (CRR/HRR) | percent (whole) | 74 | 8 | just below |
| mdt_chc-15 | Customers kept (CRR/HRR) | percent (whole) | 65 | 8 | at threshold |
| mdt_chc-16 | Customers kept (CRR/HRR) | percent (whole) | 64 | 0 | just below |
| mdt_chc-17 | New accounts (NBD) | attainment % | 81 | 15 | at threshold |
| mdt_chc-18 | New accounts (NBD) | attainment % | 80.9 | 13 | just below |
| mdt_chc-19 | New accounts (NBD) | attainment % | 66 | 13 | at threshold |
| mdt_chc-20 | New accounts (NBD) | attainment % | 65.9 | 10 | just below |
| mdt_chc-21 | New accounts (NBD) | attainment % | 51 | 10 | at threshold |
| mdt_chc-22 | New accounts (NBD) | attainment % | 50.9 | 7 | just below |
| mdt_chc-23 | New accounts (NBD) | attainment % | 36 | 7 | at threshold |
| mdt_chc-24 | New accounts (NBD) | attainment % | 35.9 | 4 | just below |
| mdt_chc-25 | New accounts (NBD) | attainment % | 20 | 4 | at threshold |
| mdt_chc-26 | New accounts (NBD) | attainment % | 19.9 | 0 | just below |
| mdt_chc-27 | Sales days (NZSD) | percent (whole) | 95 | 15 | at threshold |
| mdt_chc-28 | Sales days (NZSD) | percent (whole) | 94 | 13 | just below |
| mdt_chc-29 | Sales days (NZSD) | percent (whole) | 90 | 13 | at threshold |
| mdt_chc-30 | Sales days (NZSD) | percent (whole) | 89 | 11 | just below |
| mdt_chc-31 | Sales days (NZSD) | percent (whole) | 80 | 11 | at threshold |
| mdt_chc-32 | Sales days (NZSD) | percent (whole) | 79 | 8 | just below |
| mdt_chc-33 | Sales days (NZSD) | percent (whole) | 70 | 8 | at threshold |
| mdt_chc-34 | Sales days (NZSD) | percent (whole) | 69 | 0 | just below |
| mdt_chc-35 | Days sales outstanding (DSO) | days | 30 | 15 | at limit |
| mdt_chc-36 | Days sales outstanding (DSO) | days | 31 | 11 | just over |
| mdt_chc-37 | Days sales outstanding (DSO) | days | 40 | 11 | at limit |
| mdt_chc-38 | Days sales outstanding (DSO) | days | 41 | 7 | just over |
| mdt_chc-39 | Days sales outstanding (DSO) | days | 50 | 7 | at limit |
| mdt_chc-40 | Days sales outstanding (DSO) | days | 51 | 3 | just over |
| mdt_chc-41 | Days sales outstanding (DSO) | days | 60 | 3 | at limit |
| mdt_chc-42 | Days sales outstanding (DSO) | days | 61 | 0 | just over |

#### B2B NBD CHC (`b2b_nbd_chc`), out of 100

| ID | KPI | Read as | x | Expected points | Case |
|---|---|---|---:|---:|---|
| b2b_nbd_chc-01 | Sales invoiced (IST) | attainment % | 90 | 30 | at threshold |
| b2b_nbd_chc-02 | Sales invoiced (IST) | attainment % | 89.9 | 21 | just below |
| b2b_nbd_chc-03 | Sales invoiced (IST) | attainment % | 75 | 21 | at threshold |
| b2b_nbd_chc-04 | Sales invoiced (IST) | attainment % | 74.9 | 13 | just below |
| b2b_nbd_chc-05 | Sales invoiced (IST) | attainment % | 60 | 13 | at threshold |
| b2b_nbd_chc-06 | Sales invoiced (IST) | attainment % | 59.9 | 0 | just below |
| b2b_nbd_chc-07 | Sales invoiced (IST) (gate) | attainment % | 59.9 | — | month total capped at 40 |
| b2b_nbd_chc-08 | New accounts (NBD) | attainment % | 100 | 30 | at threshold |
| b2b_nbd_chc-09 | New accounts (NBD) | attainment % | 99.9 | 22 | just below |
| b2b_nbd_chc-10 | New accounts (NBD) | attainment % | 75 | 22 | at threshold |
| b2b_nbd_chc-11 | New accounts (NBD) | attainment % | 74.9 | 12 | just below |
| b2b_nbd_chc-12 | New accounts (NBD) | attainment % | 50 | 12 | at threshold |
| b2b_nbd_chc-13 | New accounts (NBD) | attainment % | 49.9 | 0 | just below |
| b2b_nbd_chc-14 | Days sales outstanding (DSO) | days | 70 | 20 | at limit |
| b2b_nbd_chc-15 | Days sales outstanding (DSO) | days | 71 | 10 | just over |
| b2b_nbd_chc-16 | Days sales outstanding (DSO) | days | 89 | 10 | at limit |
| b2b_nbd_chc-17 | Days sales outstanding (DSO) | days | 90 | 0 | just over |
| b2b_nbd_chc-18 | Customers kept (CRR/HRR) | percent (whole) | 95 | 10 | at threshold |
| b2b_nbd_chc-19 | Customers kept (CRR/HRR) | percent (whole) | 94 | 8 | just below |
| b2b_nbd_chc-20 | Customers kept (CRR/HRR) | percent (whole) | 85 | 8 | at threshold |
| b2b_nbd_chc-21 | Customers kept (CRR/HRR) | percent (whole) | 84 | 5 | just below |
| b2b_nbd_chc-22 | Customers kept (CRR/HRR) | percent (whole) | 75 | 5 | at threshold |
| b2b_nbd_chc-23 | Customers kept (CRR/HRR) | percent (whole) | 74 | 0 | just below |
| b2b_nbd_chc-24 | Sales days, ₱500 and up (NZSD) | percent (whole) | 95 | 10 | at threshold |
| b2b_nbd_chc-25 | Sales days, ₱500 and up (NZSD) | percent (whole) | 94 | 8 | just below |
| b2b_nbd_chc-26 | Sales days, ₱500 and up (NZSD) | percent (whole) | 90 | 8 | at threshold |
| b2b_nbd_chc-27 | Sales days, ₱500 and up (NZSD) | percent (whole) | 89 | 6 | just below |
| b2b_nbd_chc-28 | Sales days, ₱500 and up (NZSD) | percent (whole) | 80 | 6 | at threshold |
| b2b_nbd_chc-29 | Sales days, ₱500 and up (NZSD) | percent (whole) | 79 | 4 | just below |
| b2b_nbd_chc-30 | Sales days, ₱500 and up (NZSD) | percent (whole) | 70 | 4 | at threshold |
| b2b_nbd_chc-31 | Sales days, ₱500 and up (NZSD) | percent (whole) | 69 | 0 | just below |

#### B2B CRR CHC (`b2b_crr_chc`), out of 100

| ID | KPI | Read as | x | Expected points | Case |
|---|---|---|---:|---:|---|
| b2b_crr_chc-01 | Sales invoiced (IST) | attainment % | 90 | 30 | at threshold |
| b2b_crr_chc-02 | Sales invoiced (IST) | attainment % | 89.9 | 21 | just below |
| b2b_crr_chc-03 | Sales invoiced (IST) | attainment % | 75 | 21 | at threshold |
| b2b_crr_chc-04 | Sales invoiced (IST) | attainment % | 74.9 | 13 | just below |
| b2b_crr_chc-05 | Sales invoiced (IST) | attainment % | 60 | 13 | at threshold |
| b2b_crr_chc-06 | Sales invoiced (IST) | attainment % | 59.9 | 0 | just below |
| b2b_crr_chc-07 | Sales invoiced (IST) (gate) | attainment % | 59.9 | — | month total capped at 40 |
| b2b_crr_chc-08 | Customers kept (CRR/HRR) | percent (whole) | 95 | 30 | at threshold |
| b2b_crr_chc-09 | Customers kept (CRR/HRR) | percent (whole) | 94 | 24 | just below |
| b2b_crr_chc-10 | Customers kept (CRR/HRR) | percent (whole) | 85 | 24 | at threshold |
| b2b_crr_chc-11 | Customers kept (CRR/HRR) | percent (whole) | 84 | 16 | just below |
| b2b_crr_chc-12 | Customers kept (CRR/HRR) | percent (whole) | 75 | 16 | at threshold |
| b2b_crr_chc-13 | Customers kept (CRR/HRR) | percent (whole) | 74 | 0 | just below |
| b2b_crr_chc-14 | Days sales outstanding (DSO) | days | 70 | 20 | at limit |
| b2b_crr_chc-15 | Days sales outstanding (DSO) | days | 71 | 10 | just over |
| b2b_crr_chc-16 | Days sales outstanding (DSO) | days | 89 | 10 | at limit |
| b2b_crr_chc-17 | Days sales outstanding (DSO) | days | 90 | 0 | just over |
| b2b_crr_chc-18 | Cross-sell accounts | attainment % | 100 | 10 | at threshold |
| b2b_crr_chc-19 | Cross-sell accounts | attainment % | 99.9 | 7 | just below |
| b2b_crr_chc-20 | Cross-sell accounts | attainment % | 75 | 7 | at threshold |
| b2b_crr_chc-21 | Cross-sell accounts | attainment % | 74.9 | 4 | just below |
| b2b_crr_chc-22 | Cross-sell accounts | attainment % | 50 | 4 | at threshold |
| b2b_crr_chc-23 | Cross-sell accounts | attainment % | 49.9 | 0 | just below |
| b2b_crr_chc-24 | Sales days, ₱500 and up (NZSD) | percent (whole) | 95 | 10 | at threshold |
| b2b_crr_chc-25 | Sales days, ₱500 and up (NZSD) | percent (whole) | 94 | 8 | just below |
| b2b_crr_chc-26 | Sales days, ₱500 and up (NZSD) | percent (whole) | 90 | 8 | at threshold |
| b2b_crr_chc-27 | Sales days, ₱500 and up (NZSD) | percent (whole) | 89 | 6 | just below |
| b2b_crr_chc-28 | Sales days, ₱500 and up (NZSD) | percent (whole) | 80 | 6 | at threshold |
| b2b_crr_chc-29 | Sales days, ₱500 and up (NZSD) | percent (whole) | 79 | 4 | just below |
| b2b_crr_chc-30 | Sales days, ₱500 and up (NZSD) | percent (whole) | 70 | 4 | at threshold |
| b2b_crr_chc-31 | Sales days, ₱500 and up (NZSD) | percent (whole) | 69 | 0 | just below |

#### B2B DSC (`b2b_dsc`), out of 100

| ID | KPI | Read as | x | Expected points | Case |
|---|---|---|---:|---:|---|
| b2b_dsc-01 | District sales (DST) | attainment %, team | 90 | 40 | at threshold |
| b2b_dsc-02 | District sales (DST) | attainment %, team | 89.9 | 26 | just below |
| b2b_dsc-03 | District sales (DST) | attainment %, team | 75 | 26 | at threshold |
| b2b_dsc-04 | District sales (DST) | attainment %, team | 74.9 | 16 | just below |
| b2b_dsc-05 | District sales (DST) | attainment %, team | 60 | 16 | at threshold |
| b2b_dsc-06 | District sales (DST) | attainment %, team | 59.9 | 0 | just below |
| b2b_dsc-07 | District sales (DST) (gate) | attainment %, team | 59.9 | — | month total capped at 30 |
| b2b_dsc-08 | Days sales outstanding (DSO) | days, team | 70 | 20 | at limit |
| b2b_dsc-09 | Days sales outstanding (DSO) | days, team | 71 | 10 | just over |
| b2b_dsc-10 | Days sales outstanding (DSO) | days, team | 89 | 10 | at limit |
| b2b_dsc-11 | Days sales outstanding (DSO) | days, team | 90 | 0 | just over |
| b2b_dsc-12 | Team target achievement (TTAR) | attainment %, team average | 81 | 20 | at threshold |
| b2b_dsc-13 | Team target achievement (TTAR) | attainment %, team average | 80.9 | 12 | just below |
| b2b_dsc-14 | Team target achievement (TTAR) | attainment %, team average | 60 | 12 | at threshold |
| b2b_dsc-15 | Team target achievement (TTAR) | attainment %, team average | 59.9 | 0 | just below |
| b2b_dsc-16 | Team target achievement (TTAR) | attainment %, team average | one rep at 59.9% | 0 | any rep under 60% |
| b2b_dsc-17 | Customers kept (CRR/HRR) | percent (whole), team | 95 | 10 | at threshold |
| b2b_dsc-18 | Customers kept (CRR/HRR) | percent (whole), team | 94 | 8 | just below |
| b2b_dsc-19 | Customers kept (CRR/HRR) | percent (whole), team | 85 | 8 | at threshold |
| b2b_dsc-20 | Customers kept (CRR/HRR) | percent (whole), team | 84 | 5 | just below |
| b2b_dsc-21 | Customers kept (CRR/HRR) | percent (whole), team | 75 | 5 | at threshold |
| b2b_dsc-22 | Customers kept (CRR/HRR) | percent (whole), team | 74 | 0 | just below |
| b2b_dsc-23 | New accounts (NBD) | attainment %, team | 100 | 10 | at threshold |
| b2b_dsc-24 | New accounts (NBD) | attainment %, team | 99.9 | 7 | just below |
| b2b_dsc-25 | New accounts (NBD) | attainment %, team | 75 | 7 | at threshold |
| b2b_dsc-26 | New accounts (NBD) | attainment %, team | 74.9 | 4 | just below |
| b2b_dsc-27 | New accounts (NBD) | attainment %, team | 50 | 4 | at threshold |
| b2b_dsc-28 | New accounts (NBD) | attainment %, team | 49.9 | 0 | just below |


### 5.2 Caps, gates and totals

| ID | Card | Setup | Expected |
|---|---|---|---|
| CAP-01 | B2B NBD CHC | IST attainment 59.9%, all other items full (70) | IST 0 points; total 70 capped at **40**; band Below standard |
| CAP-02 | B2B NBD CHC | IST 60.0%, others full | IST 13; total 83; no cap; **Proficient** (75 ≤ 83 < 85) |
| CAP-03 | B2B CRR CHC | IST 59.9% | capped at 40 |
| CAP-04 | B2B DSC | DST 59.9%, others full | capped at **30** |
| CAP-05 | B2B DSC | TTAR: team average 85% but one rep at 59.9% | TTAR component **0** |
| CAP-06 | RX Field CHC | Gatekeeper set = 30 points (three of five met), PAP 25, HIT 15 | total 70 of 90 → capped at 70 (D-01 decides 70 points vs 70%) |
| CAP-07 | RX Field CHC | TDC attainment 79.9% of 80, everything else full | TDC 0; capped at 70 (D-01) |
| CAP-08 | RX Field CHC | Gatekeeper exactly 40 (four of five) and TDC met | no gatekeeper cap |
| CAP-09 | Any | Two caps apply (e.g. 40 and 70) | the lower cap wins (`min` of caps) |
| CAP-10 | Any | No item has a result | percent and band are **empty**, not 0 / Below standard |

### 5.3 Acceptance test: the Ria worked example (must pass unchanged)

| Step | Input | Expected |
|---|---|---|
| RIA-01 | B2B NBD CHC, September 2026 (26 working days Mon–Sat); IST target ₱10,000, NBD quota 1 | card `b2b_nbd_chc` |
| RIA-02 | Invoices: c1 ₱4,000 (2nd), c2 ₱4,000 (3rd, c2's first sale ever), c1 ₱4,000 (4th), c9 void (5th) | IST ₱12,000 = 120% → **30/30**; the void doesn't count |
| RIA-03 | First sale of c2 this month | NBD 1 of 1 = 100% → **30/30** |
| RIA-04 | ₱6,000 owed over ₱12,000 sold in 30 days | DSO 15 → **20/20** |
| RIA-05 | August customers c1 and c3; c1 bought again | CRR 50% → **0/10** |
| RIA-06 | Days with an invoice ≥ ₱500: 3 of 26 | NZSD 12% (rounded) → **0/10** |
| RIA-07 | Total | **80**, Proficient, 6% indicative raise |
| RIA-08 | Same month with IST target ₱30,000 | IST 40% → 0 points; month **capped at 40**; Below standard (PIP flag per D-14) |

Existing coverage: `tests/test_scorecards.py` asserts RIA-01 to RIA-08 today.

### 5.4 Credit holds

| ID | Setup | Expected |
|---|---|---|
| CR-01 | Customer with nothing owed | Good standing |
| CR-02 | Open invoice due in 3 days | Approaching due |
| CR-03 | Oldest unpaid invoice 1 day late | Overdue |
| CR-04 | Oldest unpaid 91 days late (and others 10 days late) | **Suspended** (precedence over Overdue) |
| CR-05 | Exactly 90 days late | Overdue (suspended is *over* 90) |
| CR-06 | New B2B quote | credit snapshot stored on the quote; it appears under Quotes → Credit to confirm |
| CR-07 | Finance puts it on hold, rep tries to raise the order | **409**, order not created; audit `quote.credit_hold` |
| CR-08 | Finance confirms, rep raises the order | order created |
| CR-09 | No decision yet, rep raises the order | today: order created; after P3-01: **409** (D-09) |
| CR-10 | Confirmed, then the customer becomes Suspended before ordering | after P3-02: a new decision is required |
| CR-11 | Non-B2B team's quote | no credit check |
| CR-12 | Finance unreachable when the quote is made | status **Not checked** (`trade.credit_check`), quote waits in the queue for a decision (never a silent Good standing) |

### 5.5 Finance attribution and synchronisation

| ID | Setup | Expected |
|---|---|---|
| FA-01 | Draft invoice for Ria | not counted in IST, NZSD, NBD, CRR |
| FA-02 | Issued, then paid | counted once, as issued |
| FA-03 | Issued, then voided | not in IST; counted in OCR (B2C) |
| FA-04 | Invoice made while Ria owns the customer; customer moved to Rex next week | still Ria's |
| FA-05 | Invoice with no salesperson | nobody's; listed for backfill (D-16) |
| FA-06 | Reissued invoice (void + replacement) | only the replacement counts |
| FA-07 | Finance down | sales items "No result yet", `financeLinked` false; never 0 |
| FA-08 | Month closed (P1-04), then Finance corrects an invoice | closed month unchanged; open month updated; correction visible in the feed's audit |
| FA-09 | B2B NZSD with two ₱300 invoices on one day | day not counted (per invoice, D-06) |
| FA-10 | B2B NBD customer last invoiced 75 days ago buys again | counted as NBD after P2-01 (D-07) |

### 5.6 RX field and patient assistance

| ID | Setup | Expected |
|---|---|---|
| RX-01 | Application approved without a receipt number | refused (422) |
| RX-02 | Approved in October, filed in September | counts for October |
| RX-03 | Denied, sent again, approved | one point, in the approval month |
| RX-04 | Pending 8 days | follow-up flag shown |
| RX-05 | Agent visits 64 different doctors of 80 | TDC 80% → 10 points, no cap |
| RX-06 | Visits to hospitals and pharmacists | not counted in TDC after P4-01 |
| RX-07 | Tier 1 doctor with 3 visits | not in DOT's numerator (P4-04) |
| RX-08 | Plan auto-fill | red first, at most 8 calls a day, Monday to Friday, tier visits respected |

---

## 6. Order of work

1. Answer §1 (D-01, D-03, D-04, D-07, D-09 and D-11 first: they change scores or controls).
2. Phase 1 (P1-01 to P1-04), then Phase 3 (P3-01, P3-02): small, high-impact.
3. Phase 2 (P2-01, P2-05), Phase 4 (P4-01, P4-02).
4. Phase 1 remainder (versions, editor, yearly average), reports, integrations.
