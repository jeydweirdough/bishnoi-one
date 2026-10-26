# Bishnoi One CRM: benchmark analysis (RX Business and B2B)

**Company:** GetMeds Philippines · **Prepared:** 25 October 2026 · **Phase:** 1 (documentation only; no application code, data or schema was changed)
**Source of truth:** the business requirements of 25 October 2026 ("REA Benchmarking & Business Requirements").
**Companion:** [implementation-roadmap.md](implementation-roadmap.md) (decisions D-01 to D-20, phases, acceptance criteria, tests).

---

## 1. Method, and what it can and can't claim

- **REA (Reverse Engineer Anything) is not available on this machine.** It isn't on the PATH (`rea`, `reverse-engineer-anything`), nor among the installed Claude plugins. So no REA output is used. The analysis uses:
  - **Twenty and Odoo:** their public source on GitHub. Each file path cited below was opened on GitHub (Odoo branch `18.0`, Twenty `main`). Nothing was cloned or copied.
  - **Salesforce, SAP, Veeva, HubSpot, Apollo, Marg, Oojeema:** public official documentation (help centers, product pages). No logins, trials or paywalled content.
  - **Bishnoi One:** the repository itself (commit `0b2a686` plus the uncommitted sidebar and report-kit work). Every "built" or "missing" below cites the file.
- **Confidence.** Rows marked *confirmed* have an official source; some were confirmed from the official page's content as indexed by search rather than a full read, and are worth a second look before a contractual decision. *Partial* means the source covers part of the claim; *unconfirmed* means no public evidence was found (not that the feature is absent). Marg and Oojeema publish little technical documentation.
- **No proprietary code or confidential data was used.** Patterns are described, not copied.

---

## 2. Nine-product comparison matrix (against the GetMeds requirements)

Cells: what the product does for that requirement area. **Bishnoi One** is today's implementation with its evidence.

| Requirement area | Salesforce | SAP | Odoo (CE) | Marg | Veeva | HubSpot | Twenty | Oojeema | Apollo | **Bishnoi One today** |
|---|---|---|---|---|---|---|---|---|---|---|
| Configurable weighted scorecards, bands, caps | Quotas and forecasts; Spiff tier and range-lookup payouts | Incentive Management rules (credit, measurement, incentive, deposit) and rate tables | Gamification goal definitions (count/sum/manual, higher/lower better), monthly challenges | Salesman reports only | Cycle plans, MyInsights dashboards | Goals per user/team, gap vs goal in forecast | none | none | Lead score model | **Built**: 12 cards, 26 KPIs, bands, item caps and group caps, team and team-average scopes (`app/scorecards.py`, `tools/seed_scorecards.py`). Gaps: no month snapshots, no versions, edited only through the seed, 90-point cap semantics (D-01), missing results score 0 (D-04) |
| Historical scorecards | Forecast history (unconfirmed detail) | rate tables per period (partial) | goal history per challenge period | — | — | goal reports | — | — | — | **Missing**: scores recomputed live from Finance each time |
| Sales attribution | Opportunity owner, splits (revenue 100%, overlay any) | credit rules and territories | `crm.team.invoiced` from posted, paid invoices, refunds netted; `account.move.invoice_user_id` | salesman-wise bills (partial) | unconfirmed | deal owner | opportunity owner (partial) | — | deal owner | **Built**: Finance invoice issued (sent or paid) for `salesperson_id`, taken from the CRM owner when invoiced and frozen there (`nbfi_invoices.salesperson_id`; `/integration/sales`; CRM `kpis._issued`). Draft and void excluded. No credit notes in Finance yet |
| Doctor segmentation, call plans, visits, GPS | LSC visit planning, offline | GPS check-in, optional proximity validation, route planner, offline | none in CE | eOrder app, map of retailers | cycle plans, call reports, GPS check-in, offline | n/a | n/a | n/a | n/a | **Built**: tiers 4/2/1, zones red/yellow/green by time of day, 8 calls a day Mon–Fri, coach review, 80% coverage; visits with products in order, message, reaction, next objective, Patient Care Group, GPS and accuracy (`routers/field.py`, `field_plan.py`, `models.Visit`). Missing: offline (decided ADAPT, not built), proximity validation |
| Patient assistance with evidence | approval lock (no file gate found) | unconfirmed | chatter, no gate | — | signature on call reports | required fields by stage (files: no source) | attachments object | — | — | **Built**: approved only with receipt, month = approval date, attachments, weekly follow-up (`routers/assistance.py`). Gap: attachments typed only `id`/`document` (D-15) |
| Customer lifecycle: reactivation, retention, cross-sell | unconfirmed | unconfirmed | recurring plans, DSO | — | — | lifecycle stage (unconfirmed) | — | AR aging | — | **Partial**: retention windows (`routers/retention.py`); CRR month over month; NBD = first sale ever (no reactivation, D-07); cross-sell entered by hand |
| Credit holds on quote-to-order | unconfirmed (not native to Sales Cloud) | **negative check blocks sales and delivery documents; Documented Credit Decision with release/reject/recheck; OData APIs** | credit limit **warning only** on draft quotes | **per-customer limit: warn or stop billing** | n/a | n/a | n/a | not stated | n/a | **Built**: status from Finance (Suspended > Overdue > Approaching > Good), snapshot on every B2B quote, Finance confirms or holds, hold blocks ordering, queue (`app/trade.py`, `routers/quotes.py`). Gap: an undecided quote can still be ordered (D-09); no amount-based credit limit |
| Stock, batches, expiry, purchasing, receiving, warehouses | samples only (LSC) | batch determination by shelf life, SLED list, FEFO in EWM | lots, expiry/removal/alert dates, FEFO by removal date, alert activities (`product_expiry`) | batch and expiry, near-expiry alerts | sample lots, transfers, counts | n/a | n/a | basic stock (Premium) | n/a | **Built (Inventory)**: batches, expiry, FEFO picking, serials, purchase orders, goods receipts, transfers, counts, adjustments, alerts, CPR, 17 reports |
| Permissions | org-wide defaults + sharing rules, role hierarchy | not researched | `ir.rule` record rules | — | — | All / Team / Own, property permissions | object, field and row-level permissions | roles | permission profiles | **Built**: `area.action` permissions + own/team/all scope (CRM `scope.py`); central roles on Platform (R1) |
| Audit trail / field history | field history 20/object, Field Audit Trail | DCD keeps the decision's data | `mail.tracking.value` old and new values | — | — | permission history | timeline (detail unchecked) | not stated | — | **Built**: audit log in every API, field names never values (by rule) |
| Reporting | report builder, dashboards | — | pivot, graph views | "1000+ MIS reports" (claim) | MyInsights | report builder | dashboards module | BIR reports | analytics | **Built**: shared report kit (`src/platform/reports/`); Inventory 17 reports; CRM people and retention reports |
| Automation and integrations | flows, APIs | OData | automated actions, XML-RPC | — | Engage | workflows | workflows (record, schedule, webhook triggers), outbound webhooks | DAT export | workflows, API | **Partial**: app-to-app APIs with keys, inbound lead webhooks; no general automation engine or outbound webhooks |

---

## 3. Evidence by product (sources)

### Odoo (Community source, branch 18.0)
- Monthly invoiced amount against a team target: `addons/sale/models/crm_team.py` (`invoiced`, `invoiced_target`; posted invoices in payment states in_payment/paid/reversed, signed untaxed amount, refunds net). https://github.com/odoo/odoo/blob/18.0/addons/sale/models/crm_team.py
- KPI definitions as data: `addons/gamification/models/gamification_goal_definition.py`, challenges `gamification_challenge.py`. https://github.com/odoo/odoo/blob/18.0/addons/gamification/models/gamification_goal_definition.py
- Salesperson on the invoice: `addons/account/models/account_move.py` (`invoice_user_id`). https://github.com/odoo/odoo/blob/18.0/addons/account/models/account_move.py
- Credit limit warning (not a block): `addons/account/models/partner.py`, `addons/sale/models/res_partner.py` (`credit_to_invoice`), `addons/sale/models/sale_order.py` (`partner_credit_warning`). https://github.com/odoo/odoo/blob/18.0/addons/sale/models/res_partner.py
- Lots and expiry: `addons/stock/models/`, `addons/product_expiry/models/production_lot.py`. https://github.com/odoo/odoo/blob/18.0/addons/product_expiry/models/production_lot.py
- Record rules and field tracking: `odoo/addons/base/models/ir_rule.py`, `addons/mail/models/mail_tracking_value.py`.
- `hr_appraisal` is not in Community (404).

### Twenty (main)
- Views (`engine/metadata-modules/view`, `view-filter`, `view-sort`, `view-permissions`), permissions (`role`, `object-permission`, `record-permissions`, `row-level-permission-predicate`), workflows (`modules/workflow/`: trigger, executor, runner, wait). https://github.com/twentyhq/twenty/tree/main/packages/twenty-server/src
- Permissions guide: https://docs.twenty.com/user-guide/permissions-access/capabilities/permissions · Workflow triggers: https://docs.twenty.com/user-guide/workflows/capabilities/workflow-triggers · Import/export: https://docs.twenty.com/user-guide/data-migration/overview · Webhooks: https://docs.twenty.com/developers/extend/webhooks

### SAP
- Credit block and Documented Credit Decision: https://help.sap.com/docs/SAP_S4HANA_CLOUD/918bca53037f408f91a2295d04ac16bc/65cfbd70e1f344afa2ba9183c315c44a.html · https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/7b24a64d9d0941bda1afa753263d9e39/ab7f7d00ce2f4d0ea8838e11a1ee6388.html
- Visit check-in with GPS and proximity: https://help.sap.com/docs/sap-cloud-for-customer/solution-guide-for-sap-sales-cloud/check-in-to-visits
- Incentive Management rules (partial): https://help.sap.com/docs/SAP_Commissions/85ce2a3717a644afa2bbd21f70387549/724ac5697c231014a804993ce4041860.html
- Shelf-life batch determination: https://help.sap.com/docs/SAP_ERP/96bf9ad642cf4b26a29595e3d573fb8c/c763bd534f22b44ce10000000a174cb4.html

### Salesforce
- Quotas and forecast types: https://help.salesforce.com/s/articleView?language=en_US&id=sf.forecasts3_quotas_intro.htm&type=5
- Opportunity splits: https://resources.docs.salesforce.com/latest/latest/en-us/sfdc/pdf/team_selling_implementation_guide.pdf
- Spiff accelerators: https://trailhead.salesforce.com/content/learn/modules/accelerators-in-salesforce-spiff-quick-look/explore-accelerator-functions-in-salesforce-spiff
- Sharing model and field history: https://help.salesforce.com/s/articleView?language=en_US&id=platform.security_sharing_owd_about.htm&type=5
- Life Sciences Cloud visits (partial): https://help.salesforce.com/s/articleView?id=ind.lsc_visit_management_get_ready.htm&language=en_US&type=5

### Veeva
- GPS check-in: https://crmhelp.veeva.com/doc/Content/CRM_topics/Activities/Call_Reporting_2/AdvFunct/Submitting/GPSCheckIn.htm
- Call planning and call reports: https://crmhelp.veeva.com/doc/Content/CRM_topics/Scheduling_Planning/CallPlanning/CPOverview.htm
- Offline validation rules: https://crmhelp.veeva.com/doc/Content/CRM_topics/Getting_Started/MobileDeviceSetup/OfflineValidationRules.htm
- Sample management and signatures: https://crmhelp.veeva.com/doc/Content/CRM_topics/SampleManagement/SMOverview.htm

### HubSpot
- Goals and forecast gap: https://knowledge.hubspot.com/reports/create-sales-goals · https://knowledge.hubspot.com/forecast/use-the-forecast-tool
- Required properties by stage, pipeline rules: https://knowledge.hubspot.com/object-settings/set-up-and-customize-pipelines · https://knowledge.hubspot.com/object-settings/set-up-pipeline-rules
- Permissions (All/Team/Own): https://knowledge.hubspot.com/user-management/hubspot-user-permissions-guide

### Marg ERP
- Credit limits (warn or strict, primary and final): https://care.margcompusoft.com/margerp/rate-and-discount-master/38672/utils/common
- Pharma batch and expiry: https://margcompusoft.com/distribution/pharma_software.html

### Oojeema
- BIR forms, DAT files, books, AR/AP aging: https://oojeema.com/ (product page; no API or audit trail stated)

### Apollo
- Scoring engine (page about four years old): https://support.apollo.io/hc/en-us/articles/360003376912-Scoring-Engine-Overview
- Deals, permissions, workflows: https://knowledge.apollo.io/hc/en-us/articles/4415062467725-Deals-Overview

---

## 4. Alignment with the RX and B2B requirements

| Requirement (section of the 25 Oct spec) | Bishnoi One | Best reference pattern | Verdict |
|---|---|---|---|
| §2 RX Field CHC vs MD Telesales CHC split (sales/NBD/CRR are MD Telesales') | Cards `rx_chc` and `mdt_chc` match; RX card has no sales items | — | **Aligned** |
| §2 B2B NBD / CRR / DSC | Cards `b2b_nbd_chc`, `b2b_crr_chc`, `b2b_dsc` match weights and bands | — | **Aligned** (NBD definition: see D-07) |
| §2 BID and CLIP separate | BID team and CLIDP (`app/clidp.py`) separate | — | **Aligned** (name "CLIP" vs CLIDP: D-20) |
| §3 Bands, raises, monthly vs yearly | Bands on monthly %, 12-month average not built, PIP any month below 60 | Salesforce/HubSpot quota periods; Odoo challenge history | **Partial** (D-13, D-14) |
| §3 Don't invent scoring for missing data, gaps, rounding | Missing manual counts score 0; banker's rounding; attainment to 0.1 | Odoo goal states (no result vs failed) | **Gap** (D-03, D-04) |
| §4.1 RX 90-point card, gatekeeper set, caps | Implemented; cap applied as 70 points of 90 (77.8%) | — | **Needs decision** (D-01, D-02) |
| §4.1 TDC 80% of a list of 80 | Fixed 80, counts all accounts visited | Veeva cycle plan targets per territory | **Gap** (D-11) |
| §4.1 HIT quarterly | Scored monthly | Salesforce/HubSpot quarter quotas | **Gap** (D-12) |
| §4.2 MD Telesales thresholds | Exact; DSO ranges assumed between listed points | — | **Aligned** (D-05 to confirm) |
| §5 Call planning and visits | Built as specified | Veeva call reports, SAP check-in | **Aligned** (offline and proximity are extras) |
| §5 PAP from approved, receipt required, follow-up 7 days | Built (approval receipt, weekly follow-up) | HubSpot required-by-stage | **Mostly aligned** (typed attachments D-15) |
| §6 RX types and fields; hidden fields | Built (`rx_form.py`) | — | **Aligned** |
| §7 Ria example as acceptance test | `tests/test_scorecards.py` asserts it | — | **Aligned** |
| §8 Sale = Finance invoice, salesperson from CRM owner | Built; frozen at invoicing; drafts and voids excluded | Odoo `invoice_user_id`, `crm.team.invoiced` | **Aligned** (backfill D-16) |
| §8 NZSD ₱500 minimum | Per invoice | — | **Needs decision** (D-06) |
| §9 Credit status and precedence | Built; precedence Suspended > Overdue > Approaching > Good | SAP DCD | **Aligned** (D-10 to approve) |
| §9 Finance must confirm or hold; hold stops order | Hold stops order; undecided does not | SAP: document blocked until released | **Gap** (D-09) |
| §9 Trade profile, 2MG field, B2B by Credit terms teams | Built (`trade.py`, `split_b2b.py`) | — | **Aligned** |
| §9 B2B types, retired types on legacy records | Built (`is_active = False`) | — | **Aligned** |
| §10 Data sources and screens | Built as listed | — | **Aligned** |

---

## 5. Existing implementation, gaps, assumptions, unknowns

**Built and aligned:** see the roadmap §2 table (evidence by file).

**Gaps (with evidence):**
1. Month results aren't frozen: a Finance correction changes past months (`scorecards.score` recomputes from the live feed).
2. Scorecards have no versions and no editor screen; changes go through `seed_scorecards.py`.
3. Missing manual results score 0 (`kpis.value_of`).
4. RX caps read as points on a 90-point card (`scorecards.score`).
5. NBD ignores reactivations (`kpis._new_accounts`).
6. TDC denominator fixed at 80 and counts any account type (`seed_scorecards.py` `"of": 80`, `kpis._doctors_visited`).
7. HIT quarterly not modelled.
8. Undecided credit doesn't block ordering (`quotes.orderable`).
9. Patient-assistance attachments untyped (`routers/assistance.py`).
10. Constants that should be configuration: `SUSPENDED_DAYS`, `HIGH_SHARE`, `PRIORITY_SHARE`, `COVERAGE_GOAL`, `CALLS_A_DAY`.
11. No offline field work (decided ADAPT in benchmarks, G3).
12. No credit notes in Finance, so returns can't net against IST (Odoo nets refunds).

**Assumptions made in this document:** none beyond the stated proposed defaults in the roadmap's §1, each marked for approval.

**Unknowns:** native credit control in Salesforce Sales Cloud; any product's "attachment required before status" gate; dormant-customer reactivation features in any product; Marg's field app and targets; Oojeema's API, audit trail and BIR approval status (confirm with the vendor).

---

## 6. Recommendations, ranked

Impact = effect on fair scoring, controls or revenue; Risk = chance of breaking existing behaviour; Effort: S ≤ 2 days, M ≤ 1 week, L > 1 week.

| Rank | Recommendation | Pattern from | Impact | Risk | Effort | Roadmap |
|---:|---|---|---|---|---|---|
| 1 | Settle cap semantics on the 90-point RX card | — | High (a capped month can still earn Proficient) | Low | S | D-01, P1-03 |
| 2 | Block ordering until Finance decides; re-check at order time; keep the decision's data with it | SAP Documented Credit Decision | High (closes a control gap) | Low | S | D-09, P3-01, P3-02 |
| 3 | Month close with frozen results | SAP/Spiff period processing; Odoo challenge history | High (auditability, pay disputes) | Medium | M | P1-04 |
| 4 | Missing data is "No result yet", never a silent 0; truncate, don't round across thresholds | Odoo goal states | High | Low | S–M | D-03, D-04, P1-01, P1-02 |
| 5 | NBD counts reactivated (inactive, dormant) customers for B2B NBD, from Finance's feed | Odoo invoice data as source | High (B2B NBD pay) | Medium | M | D-07, P2-01 |
| 6 | TDC from each agent's doctor list and doctors only | Veeva cycle plans | Medium–High | Low | M | D-11, P4-01 |
| 7 | Scorecard versions and an editor (KPI definitions as data) | Odoo gamification goal definitions; Spiff rate tables | Medium | Medium | L | P1-05, P1-08 |
| 8 | Show the gap to target beside each attainment | HubSpot/Salesforce forecast gap | Medium | Low | S | P5 |
| 9 | Typed evidence on patient-assistance applications, optional required set | HubSpot required-by-stage | Medium | Low | S | D-15, P4-02 |
| 10 | Quarterly scoring for HIT | Salesforce/HubSpot quarterly quotas | Medium | Low | S | D-12, P1-06 |
| 11 | Company holidays and leave in NZSD (Finance already has the PH calendar) | — | Medium | Low | M | D-19, P2-03 |
| 12 | Optional amount-based credit limit with exposure (receivable + open orders) | Odoo `credit_to_invoice`, Marg warn/strict | Medium (not required by the spec) | Medium | M | proposal only |
| 13 | Credit notes in Finance netted against IST | Odoo signed amounts | Medium | Medium | M | proposal only |
| 14 | GPS proximity check on visit check-in | SAP C4C | Low–Medium | Low | S | proposal only |
| 15 | Offline visits and collections (decided ADAPT) | Veeva offline rules | Medium | High | L | benchmarks G3 |

**Present before coding:** the roadmap's §1 decisions (D-01, D-03, D-04, D-07, D-09, D-11 first) decide what is built in Phase 1.
