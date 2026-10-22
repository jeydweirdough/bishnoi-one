# BIR sales DAT

Finance → **BIR sales DAT** (`/bir/sales-dat`): builds the BIR Summary List of Sales
(RELIEF) `.DAT` from Oojeema's exports, applies the corrections Sir Rommel confirmed,
and checks the result against the Income Statement. Everything runs in the browser:
no file is uploaded.

It replaces the standalone `converter.html` (built for Sir Rommel, October 2026), which
is kept, unchanged, as the reference the tests compare against.

## Files

| File | What it is | Change it? |
|---|---|---|
| `engine.ts` | The converter's logic: reading CSV/Excel exports, matching, the corrections, the DAT, the Excel report. **Its lines 369–1417, copied byte for byte.** Not type-checked, on purpose. | Only for a ruling Sir Rommel confirms, then run the tests and update `rules.ts` |
| `prepare.ts` | Typed steps for a month (the converter's `loadReports`, `take`, `runCore`, `irExplain`), with the settings passed in instead of read off its page | Yes, with the tests |
| `rules.ts` | The rules on record, with who confirmed them and when. Shown under "Rules in use" | With every ruling |
| `index.ts` | The one door: the rest of Finance imports from here, never from `engine.ts` | |
| `screen.tsx`, `prepare-tab.tsx`, `as-is-tab.tsx`, `dat-csv-tab.tsx`, `drop.tsx`, `parts.tsx`, `download.ts` | The screen | Freely |

Each company's details for the file's first line (RDO code, year-end month) come from
the API, `GET /finance/bir/sales-dat` (backend `app/bir.py`), found by the seller TIN
in the exports. A company with no details (GPI, so far) is asked for them before a DAT
can be downloaded. Only a role with **Prepare BIR files** (`bir.prepare`) opens the page.

## Tests

```
cd bishnoi-finance/frontend
node --import ./tests/support/register.mjs --test "tests/*.test.mjs"
```

Node 24 or later; nothing to install. `tests/bir-sales-dat.test.mjs` runs the original
`converter.html` and this code on the same real Oojeema exports (March–September 2026)
and requires the same DAT byte for byte, the same corrections, open items, checks,
totals, gap explanations and Excel report, month by month.

The exports hold real customers and amounts, so they stay outside the repo, in the
converter's folder: set `BIR_CONVERTER_DIR` to it (by default, the folder
`BIR DAT Converter` beside the repo). Without it, the tests are skipped.

## Changing a rule

1. Confirm it with Sir Rommel.
2. Change `engine.ts` (and `converter.html` too, while it is still the reference).
3. Run the tests. The comparison will now differ for the months the rule touches:
   check each difference is the intended one.
4. Record it in `rules.ts`, with the date.
5. Add a line to What's new (`src/version/changes.ts`).

## Later

- **Tidy the engine into typed modules:** safe now that the tests compare every
  output with the original. Do it in small steps, running the tests after each.
- **Made from Finance's own records** (no Oojeema exports), once the Hub keeps
  2MG's sales. See the vault's "Plan - BIR converter in Finance", option C.
