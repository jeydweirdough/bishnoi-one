"use client";

import { Search } from "lucide-react";
import { useState, useTransition } from "react";
import { findCustomers } from "@/src/modules/finance/invoices/actions";
import type { Customer } from "@/src/modules/finance/invoices/types";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Input } from "@/src/modules/finance/platform/ui/field";

export function CustomerPicker({
  onSelect,
}: {
  onSelect: (c: { id: string; name: string; tin: string | null; address: string | null }) => void;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Customer[] | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [searching, startSearch] = useTransition();

  function runSearch() {
    if (!q.trim()) return;
    setNote(null);
    startSearch(async () => {
      const res = await findCustomers(q.trim());
      if (!res.ok) {
        setResults(null);
        setNote("CRM customer search isn't connected right now — you can type the customer details below.");
        return;
      }
      setResults(res.data);
      if (res.data.length === 0) setNote("No matching CRM customer found — you can still type the name below.");
    });
  }

  return (
    <div className="rounded-lg border border-rule bg-bench p-3 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-[220px] flex-1">
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                runSearch();
              }
            }}
            placeholder="Search CRM customer by name or TIN…"
            aria-label="Search CRM customer"
          />
        </div>
        <Button type="button" size="sm" loading={searching} icon={<Search className="size-3.5" aria-hidden />} onClick={runSearch}>
          Find customer
        </Button>
      </div>
      {note && <p className="text-meta text-ink-2">{note}</p>}
      {results && results.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {results.slice(0, 8).map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => {
                onSelect({ id: c.id, name: c.name, tin: c.tin, address: c.address });
                setResults(null);
                setNote(`Picked from CRM: ${c.name}`);
              }}
              className="rounded border border-control bg-sheet px-2.5 py-1 text-left text-meta text-ink hover:border-ink"
            >
              <span className="font-medium">{c.name}</span>
              {c.tin ? <span className="ml-1.5 text-ink-3">TIN {c.tin}</span> : null}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
