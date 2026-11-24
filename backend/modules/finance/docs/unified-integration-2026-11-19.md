# Unified Finance integration — 19 November 2026

## Delivered source

The local Finance branch is combined with Jade's `266871c0` unified architecture. Publication is tracked in the branch history and [PR3](https://github.com/jeydweirdough/bishnoi-one/pull/3); it is separate from deployment. Existing private database files and environment settings are not moved, upgraded or activated by this source integration. No official service, provider sending or staff grants are changed.

The unified code is under `backend/modules/{finance,inventory,platform}`. Keep the shared identity, in-process request marks, approval slips, work menu, security changes and report Save as behavior from main. Legacy per-app backend source is removed from version control; ignored historical data folders may remain on this PC and must not be recursively deleted.

Local safeguards and functionality carried forward:

- strict verified2MG supplier/account eligibility, including posting/import/consequential actions and incoming company evidence;
- supplier batch review and per-line withholding decisions;
- explicit Inventory receipt submission and versioned reply, durable intake, reviewed supplier crosswalk, partial/multiple receipt allocations, duplicate protection and draft cancellation guards;
- Finance title/action hierarchy and report-table/source-export safeguards;
- PHP-only supplier bills from Jade's newer version. Legacy FX controls/payload fields are removed. Foreign receipt evidence is retained with an explicit hold, not converted automatically.

## Confirmed fixes

### Checked spending

The expense-category summary includes only accepted, company-covered receipts whose request has completed Finance checking. Its description explicitly uses spending dates; accounting recognizes liquidation on its check date. Pending receipts and personal/noncovered spending do not appear as recognized company spending. This does not create tax metadata or make Marketing receipts BIR purchase documents.

### Product cost before invoice issuance

An invoice with product codes needs valid Inventory costs and inventory/cost-of-goods posting accounts. Unavailable or missing costs cause a hold before changing the invoice number or draft state. An explicit known zero cost is allowed and differs from an absent value. Uncoded manual lines retain explicit unknown-cost evidence; no product identity is invented. Existing margin warnings remain useful for history.

The Inventory response adapter no longer changes a missing unitCost into zero. Valid product costs are recorded with the invoice; sale/void accounting and dependent delivery events retain the existing transaction rules. Delivery-created invoices that cannot be issued remain drafts with an explanation.

### Historical cash forecast

The forecast uses the existing dated receivable/payable readers for its selected day. Later payments no longer erase balances from an earlier forecast. Cash and outstanding document inputs now use the same as-of basis.

### Source parsing

The all-module compilation check found an existing quote syntax error in the vendor-import tool. Its output formatting is corrected; the tool was not run against any database.

## Migration compatibility and data preservation

Main's Finance0036/0037 and Inventory0024-0031 keep their existing meanings. Feature additions are Finance0038/0039/0040 and Inventory0032. They preserve complete existing feature schemas and refuse partial ones.

`legacy_history.py` recognizes only the known pre-unification feature shapes. Within the verified backup/rollback boundary, it routes those histories through the common ancestor so main's intervening steps and the additive feature steps all run. It does not blindly stamp an old database to head. Mixed or incomplete histories stop; source requirements for retained foreign money remain enforced by main's migration.

Both Finance and Inventory use fresh SQLite backup-API copies, verify the backup before updating and restore through SQLite on failure. PostgreSQL uses the migration transaction/advisory lock; PostgreSQL acceptance is not claimed here.

Four private-copy upgrade rehearsals passed: Finance, the two populated Inventory tenant databases and the empty Inventory base. Every retained table's original common-column rows matched; integrity was OK and no foreign-key findings were introduced. Main intentionally removes the exchange-rate/wave tables; no such removal was applied to originals. WAL/failed-upgrade tests confirm saved rows and the old version are restored, including a failure after schema work starts.

## Validation and practical limits

- Source-only frontend TypeScript check passed against the combined tree.
- Finance screen tests:46 passed,1 skipped.
- Initial full combined Finance run:642 passed,139 skipped,8 failures. These were inspected: old0034 convergence-test timing/projections, an incorrect new category fixture and coded-product fixtures that lacked explicit costs. Fixes retain strict schema/accounting behavior. The rechecked affected files passed32 with10 skips; final Finance report/migration focused run passed31 with10 skips. These overlapping runs are not added into a fabricated total or described as one clean full rerun.
- Final receipt/PHP-only lifecycle group:16 passed. Actual emitted Inventory evidence → Finance reply → Inventory digest/status contract:3 passed.
- New legacy-history/report integrity group:12 passed. Inventory migration/WAL/refusal group:3 passed.
- Complete unified Python modules compile successfully.
- Other modules full run:923 passed,2 skipped,1 error-wording compatibility failure. Preserving the existing Inventory newer-database message resolves it; the affected migration/WAL/refusal group passes3. No broader failures were observed.
- The installed working source matches the isolated candidate tree, with no unresolved conflicts. All four original database table fingerprints were checked again after installation and remain unchanged. Source publication does not upgrade or activate the original databases.

No browser/keyboard/staff acceptance, real Q1 tie-out, PostgreSQL upgrade, tax-law applicability, filing approval or official deployment is implied by these tests. Optional cases remain skips, not passes. Dependency/date-adapter and InvoicePayment session warnings are disclosed in the test logs.

## Picking up this exact folder

Read the local-only root guide and this document first. The user authorized publication of this integration through the existing feature branch and PR3. Check the current Git status before further work; any later changes still need their own commit/push authorization. PR acceptance does not authorize deployment or database upgrades.

Use the unified `backend/pyproject.toml`, `backend/main.py`, and root README. The old test-stack command/ports are historical. Starting the backend runs migrations: do not point it at the old databases or copy legacy secrets into a new environment without a separately reviewed local rollout. No migration or launch is part of this source installation.

Staff declined the HTML reviewer. In-system approved ownership/status/equivalence review, supplier advances, Marketing sender/tax evidence, Pharmacy scope, Q1 openings/import tie-out, remaining BIR evidence/credits/adjustments and named-person acceptance remain separate work. This release fixes the demonstrated report defects and integrates existing work; it does not manufacture missing business decisions or declare the whole application finished.
