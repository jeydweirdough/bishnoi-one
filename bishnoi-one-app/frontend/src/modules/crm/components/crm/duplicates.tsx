"use client";

import Link from "next/link";
import { Button } from "@/src/platform/ui/button";
import type { Duplicate } from "@/src/platform/lib/types";

/**
 * "This looks like one already here": the matches, each linked where the person
 * can open it, and the way to add it anyway when it really is a different one.
 */
export function Duplicates({
  message,
  found,
  base,
  onAddAnyway,
  pending,
  quote = false,
}: {
  message: string;
  found: Duplicate[];
  base: "/crm/companies" | "/crm/contacts";
  onAddAnyway: () => void;
  pending: boolean;
  /** They were being added to quote: offer to quote the one already here instead. */
  quote?: boolean;
}) {
  return (
    <div role="alert" className="animate-reshape space-y-3 rounded-lg border border-rule-strong bg-bench/60 px-4 py-3">
      <p className="text-sm font-semibold text-ink">{message}</p>
      <ul className="space-y-1 text-meta">
        {found.map((d) => (
          <li key={d.id}>
            {d.canOpen === false ? (
              <span className="font-medium text-ink">{d.name}</span>
            ) : (
              <Link href={`${base}/${d.id}`} target="_blank" className="font-medium text-ink hover:underline">
                {d.name}
              </Link>
            )}
            <span className="text-ink-3">
              {[d.teamName, d.phone].filter(Boolean).map((x) => ` · ${x}`)}
              {d.canOpen === false ? " · someone else's" : ""}
            </span>
            {quote && d.canOpen !== false && (
              <Link href={`/crm/companies/${d.id}/quotes/new`} className="ml-2 font-medium text-ink hover:underline">
                Quote them instead
              </Link>
            )}
          </li>
        ))}
      </ul>
      <Button size="sm" onClick={onAddAnyway} loading={pending}>
        It&apos;s a different one, add anyway
      </Button>
    </div>
  );
}
