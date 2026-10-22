"use client";

import { useState } from "react";
import { AsIsTab } from "./as-is-tab";
import { DatCsvTab } from "./dat-csv-tab";
import { PrepareTab } from "./prepare-tab";
import type { Company } from "./index";

// The BIR Sales DAT screen: the converter's three tabs. Each keeps its own files while
// you switch between them.

const TABS = [
  ["prepare", "Prepare monthly DAT"],
  ["asis", "Convert as-is"],
  ["datcsv", "DAT to CSV"],
] as const;
type Tab = (typeof TABS)[number][0];

export function SalesDatScreen({ companies }: { companies: Company[] }) {
  const [tab, setTab] = useState<Tab>("prepare");
  return (
    <div className="space-y-5">
      <div role="tablist" className="flex flex-wrap gap-1 border-b border-rule">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-semibold ${tab === key ? "border-hema text-hema" : "border-transparent text-ink-3 hover:text-ink"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div hidden={tab !== "prepare"}><PrepareTab companies={companies} /></div>
      <div hidden={tab !== "asis"}><AsIsTab companies={companies} /></div>
      <div hidden={tab !== "datcsv"}><DatCsvTab /></div>
      <p className="max-w-3xl text-meta text-ink-3">
        <b>Before you submit:</b> run each DAT through the BIR RELIEF Validation Module (the only real test of acceptance) and submit it under its exact file name. Everything here is worked out on this computer: no file is uploaded.
      </p>
    </div>
  );
}
