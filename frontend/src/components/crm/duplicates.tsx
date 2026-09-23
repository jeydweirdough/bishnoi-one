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
}: {
  message: string;
  found: Duplicate[];
  base: "/companies" | "/contacts";
  onAddAnyway: () => void;
  pending: boolean;
}) {
  return (
    <div role="alert" className="animate-reshape space-y-3 rounded-[3px] border border-rule-strong bg-bench/60 px-4 py-3">
      <p className="text-sm font-semibold text-ink">{message}</p>
      <ul className="space-y-1 text-meta">
        {found.map((d) => (
          <li key={d.id}>
            {d.canOpen === false ? (
              <span className="font-medium text-ink">{d.name}</span>
            ) : (
              <Link href={`${base}/${d.id}`} target="_blank" className="font-medium text-hema hover:underline">
                {d.name}
              </Link>
            )}
            <span className="text-ink-3">
              {[d.teamName, d.phone].filter(Boolean).map((x) => ` · ${x}`)}
              {d.canOpen === false ? " · someone else's" : ""}
            </span>
          </li>
        ))}
      </ul>
      <Button size="sm" onClick={onAddAnyway} loading={pending}>
        It&apos;s a different one, add anyway
      </Button>
    </div>
  );
}
