"use client";

import { Pencil, Search, Trash2 } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";
import { Pager as SharedPager } from "@/src/platform/ui/pager";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Select } from "@/src/platform/ui/field";
import { deleteCompany, deleteContact } from "@/src/modules/crm/actions/crm";

type Option = { value: string; label: string };

/**
 * A search box and a few dropdowns that live in the address, so a filtered list
 * can be shared or come back to. Typing waits a moment before it searches;
 * a dropdown applies at once. Any change goes back to the first page.
 */
export function Filters({ search, selects }: { search?: string; selects: { name: string; label: string; options: Option[] }[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [, start] = useTransition();

  function go(changes: Record<string, string>) {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(changes)) (v ? next.set(k, v) : next.delete(k));
    next.delete("page");
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
      <label className="relative min-w-[14rem] flex-1">
        <span className="sr-only">Search</span>
        <Search className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={search}
          className="block h-10 w-full rounded-lg border border-control bg-sheet pr-4 pl-11 text-sm text-ink placeholder:text-ink-3/80 transition-colors hover:border-ink-3 focus:border-ink focus:shadow-[0_0_0_3px_rgb(168_214_155_/_0.45)] focus:outline-none"
        />
      </label>
      )}
      {selects.map((s) => (
        <label key={s.name} className="min-w-[10rem]">
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

/** "1–50 of 132", the page numbers, and the next and previous pages (the shared pager, by address). */
export function Pager({ total, page, size, base }: { total: number; page: number; size: number; base: string }) {
  return <SharedPager total={total} page={page} size={size} base={base} />;
}

/** Deleting a company or a contact, from its own page. */
/** What a record page's name can do to the record itself, as icons beside the name. */
const ICON = "inline-flex size-8 shrink-0 items-center justify-center rounded-md text-ink-3 transition-colors";

export function EditRecord({ href, what }: { href: string; what: string }) {
  return (
    <Link href={href} aria-label={`Edit ${what}`} title={`Edit ${what}`} className={`${ICON} hover:bg-hema-tint hover:text-ink`}>
      <Pencil className="size-4" aria-hidden />
    </Link>
  );
}

export function DeleteRecord({ kind, id, name, body }: { kind: "company" | "contact"; id: string; name: string; body: string }) {
  const router = useRouter();
  const what = kind === "company" ? "customer" : "contact";
  return (
    <ConfirmButton
      label={<span className="sr-only">Delete {what}</span>}
      icon={<Trash2 className="size-4" aria-hidden />}
      triggerTitle={`Delete ${what}`}
      triggerClassName="!size-8 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger"
      title={`Delete ${name}?`}
      body={body}
      confirmLabel={`Delete ${kind === "company" ? "customer" : kind}`}
      triggerVariant="quiet"
      triggerSize="sm"
      onConfirm={async () => {
        const result = kind === "company" ? await deleteCompany(id) : await deleteContact(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(`${kind === "company" ? "Customer" : "Contact"} deleted`, { description: name });
        router.push(kind === "company" ? "/crm/companies" : "/crm/contacts");
        router.refresh();
      }}
    />
  );
}
