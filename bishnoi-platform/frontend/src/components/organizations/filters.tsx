"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { Select } from "@/src/platform/ui/field";

type Option = { value: string; label: string };

/**
 * A search box and a few dropdowns that live in the address, so a filtered
 * list can be shared or come back to. Typing waits a moment before it
 * searches; a dropdown applies at once.
 */
export function Filters({ search, selects = [] }: { search?: string; selects?: { name: string; label: string; options: Option[] }[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [, start] = useTransition();

  function go(changes: Record<string, string>) {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(changes)) (v ? next.set(k, v) : next.delete(k));
    start(() => router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false }));
  }

  useEffect(() => {
    if (q === (params.get("q") ?? "")) return;
    const t = setTimeout(() => go({ q: q.trim() }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  return (
    <div className="mb-4 flex flex-wrap items-end gap-3">
      {search && (
        <label className="relative min-w-[min(14rem,100%)] flex-1">
          <span className="sr-only">Search</span>
          <Search className="pointer-events-none absolute top-1/2 left-0 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={search}
            className="block h-9 w-full border-0 border-b border-control bg-transparent pl-6 text-sm text-ink placeholder:text-ink-3/80 focus:border-hema focus:shadow-[inset_0_-1px_0_var(--color-hema)] focus:outline-none"
          />
        </label>
      )}
      {selects.map((s) => (
        <label key={s.name} className="min-w-[min(10rem,100%)]">
          <span className="mb-1 block text-meta font-medium text-ink-2">{s.label}</span>
          <Select value={params.get(s.name) ?? ""} onChange={(e) => go({ [s.name]: e.target.value })}>
            {s.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </label>
      ))}
    </div>
  );
}
