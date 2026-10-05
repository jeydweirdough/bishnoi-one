"use client";

import { ChevronDown, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { Spinner } from "@/src/platform/ui/button";
import { CUSTOMER_STATUSES, pickable } from "@/src/platform/lib/labels";
import type { ListItem } from "@/src/platform/lib/types";

function FilterSelect({ label, value, onChange, children }: { label: string; value: string; onChange: (v: string) => void; children: React.ReactNode }) {
  return (
    <span className="relative">
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 min-w-0 appearance-none rounded-[6px] border border-rule-strong bg-sheet pr-8 pl-2.5 text-sm text-ink hover:border-control focus:border-hema focus:outline-none"
      >
        {children}
      </select>
      <ChevronDown aria-hidden className="pointer-events-none absolute top-1/2 right-2 size-4 -translate-y-1/2 text-ink-3" />
    </span>
  );
}

// `kinds`: the company's own customer kinds, handed down by the page that loaded them.
// `divisions`: empty for anyone who sells in only one — there is nothing to tell apart.
export function CustomerFilters({
  teams,
  divisions,
  kinds,
}: {
  // A team code is only unique inside its division, so each team names both.
  teams: { code: string; name: string; division: string; divisionName: string }[];
  divisions: { code: string; name: string }[];
  kinds: ListItem[];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, start] = useTransition();
  const [q, setQ] = useState(params.get("q") ?? "");
  const typing = useRef<ReturnType<typeof setTimeout>>(undefined);

  function apply(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    next.delete("page"); // a new filter starts from the first page
    start(() => router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false }));
  }

  useEffect(() => () => clearTimeout(typing.current), []);

  // Teams of the chosen division only: offering the rest would be offering a
  // filter that can only ever return nothing.
  const chosen = params.get("division") ?? "";
  const shownTeams = chosen ? teams.filter((t) => t.division === chosen) : teams;

  function onSearch(value: string) {
    setQ(value);
    clearTimeout(typing.current);
    typing.current = setTimeout(() => apply({ q: value.trim() }), 300);
  }

  return (
    <div role="search" className="flex flex-wrap items-center gap-2">
      <label className="relative min-w-0 flex-1 basis-56">
        <span className="sr-only">Search customers</span>
        <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-3" />
        <input
          type="search"
          value={q}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Name, city, specialty or phone"
          className="h-9 w-full rounded-[6px] border border-rule-strong bg-sheet pr-3 pl-8 text-sm placeholder:text-ink-3/80 hover:border-control focus:border-hema focus:outline-none"
        />
      </label>
      {divisions.length > 1 && (
        <FilterSelect
          label="Division"
          value={params.get("division") ?? ""}
          // Changing division drops a team filter that belonged to the old one.
          onChange={(v) => apply({ division: v, team: "" })}
        >
          <option value="">All your divisions</option>
          {divisions.map((d) => (
            <option key={d.code} value={d.code}>
              {d.name}
            </option>
          ))}
        </FilterSelect>
      )}
      {shownTeams.length > 1 && (
        <FilterSelect
          label="Team"
          value={params.get("team") ?? ""}
          // A team belongs to a division, so picking one sets both: the API
          // cannot look a team up without knowing where it is.
          onChange={(v) => apply({ team: v, division: v ? (shownTeams.find((t) => t.code === v)?.division ?? "") : (params.get("division") ?? "") })}
        >
          <option value="">All your teams</option>
          {shownTeams.map((t) => (
            <option key={`${t.division}:${t.code}`} value={t.code}>
              {divisions.length > 1 ? `${t.divisionName} · ${t.name}` : t.name}
            </option>
          ))}
        </FilterSelect>
      )}
      <FilterSelect label="Status" value={params.get("status") ?? ""} onChange={(v) => apply({ status: v })}>
        <option value="">Any status</option>
        {Object.entries(CUSTOMER_STATUSES).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </FilterSelect>
      <FilterSelect label="Type" value={params.get("kind") ?? ""} onChange={(v) => apply({ kind: v })}>
        <option value="">Any type</option>
        {pickable(kinds).map((k) => (
          <option key={k.code} value={k.code}>
            {k.name}
          </option>
        ))}
      </FilterSelect>
      <span aria-live="polite" className="inline-flex w-5 justify-center text-ink-3">
        {pending && <Spinner />}
        <span className="sr-only">{pending ? "Updating results" : ""}</span>
      </span>
    </div>
  );
}
