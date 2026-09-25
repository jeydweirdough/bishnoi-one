"use client";

import { FilePlus2, Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Button } from "@/src/platform/ui/button";
import { findCustomers } from "../../actions/crm";

type Customer = { id: string; name: string };

/**
 * "New quote" from anywhere: a quote is always for a customer, so this asks
 * which one first (type to find them), then opens that customer's quote form.
 * The first page of customers is at hand; typed words search them all.
 */
export function NewQuoteButton({ customers, variant = "primary", label = "New quote" }: { customers: Customer[]; variant?: "primary" | "default"; label?: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const router = useRouter();
  const titleId = useId();
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Customer[] | null>(null);
  const local = useMemo(() => {
    const words = q.trim().toLowerCase();
    return (words ? customers.filter((c) => c.name.toLowerCase().includes(words)) : customers).slice(0, 50);
  }, [q, customers]);
  // Past what's at hand, ask the API (a moment after the typing stops).
  useEffect(() => {
    const words = q.trim();
    if (words.length < 2) return setFound(null);
    const wait = setTimeout(async () => {
      const result = await findCustomers(words);
      if (result.ok) setFound(result.data);
    }, 250);
    return () => clearTimeout(wait);
  }, [q]);
  const shown = found ?? local;

  return (
    <>
      <Button variant={variant} icon={<FilePlus2 className="size-4" aria-hidden />} onClick={() => dialog.current?.showModal()}>
        {label}
      </Button>
      <dialog ref={dialog} aria-labelledby={titleId} className="m-auto w-[min(30rem,calc(100vw-2rem))] rounded-[3px] bg-sheet p-0 text-ink shadow-overlay backdrop:bg-ink/30">
        <div className="flex items-center justify-between border-b border-rule px-5 py-3">
          <h2 id={titleId} className="text-heading">
            New quote for…
          </h2>
          <button type="button" onClick={() => dialog.current?.close()} className="rounded-[3px] p-1 text-ink-3 hover:bg-bench hover:text-ink" aria-label="Close">
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="px-5 pt-3 pb-4">
          <label className="flex items-center gap-2 border-b border-rule-strong pb-1.5 focus-within:border-hema">
            <Search className="size-4 text-ink-3" aria-hidden />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Type a customer's name"
              aria-label="Find a customer"
              autoFocus
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>
          {customers.length === 0 ? (
            <p className="py-6 text-center text-meta text-ink-3">You have no customers yet. Add one first, then quote them.</p>
          ) : shown.length === 0 ? (
            <p className="py-6 text-center text-meta text-ink-3">No customer called that.</p>
          ) : (
            <ul className="mt-2 max-h-80 overflow-y-auto">
              {shown.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => {
                      dialog.current?.close();
                      router.push(`/companies/${c.id}/quotes/new`);
                    }}
                    className="w-full rounded-[3px] px-2 py-2 text-left text-sm hover:bg-hema-tint hover:text-hema"
                  >
                    {c.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </dialog>
    </>
  );
}
