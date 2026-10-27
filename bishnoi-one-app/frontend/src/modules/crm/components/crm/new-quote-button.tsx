"use client";

import { Modal } from "antd";
import { FilePlus2, Search, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/src/platform/ui/button";
import { useCan } from "@/src/modules/crm/components/quick-add/can";
import { findCustomers } from "@/src/modules/crm/actions/crm";
import { AddCustomer } from "@/src/modules/crm/components/quick-add/forms";
import { QuickAddWindow } from "@/src/modules/crm/components/quick-add/quick-add";

type Customer = { id: string; name: string };

/**
 * "New quote" from anywhere: a quote is always for a customer, so this asks
 * which one first (type to find them), then opens that customer's quote form.
 * The first page of customers is at hand; typed words search them all.
 * Someone not on the list yet can be added from here, and the quote follows.
 */
export function NewQuoteButton({ customers, variant = "primary", label = "New quote" }: { customers: Customer[]; variant?: "primary" | "default"; label?: string }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
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
  const mayAdd = useCan()("customers.create");
  const typed = q.trim();
  // Adding someone new right here, by name (their details follow on their page), then straight on to their quote.
  const [adding, setAdding] = useState(false);
  const addNew = () => setAdding(true);
  const quoteFor = (c: Customer) => {
    setOpen(false);
    router.push(`/crm/customers/${c.id}/quotes/new`);
  };
  const addButton = (text: string) =>
    mayAdd && (
      <Button variant="primary" size="sm" icon={<UserPlus className="size-4" aria-hidden />} onClick={addNew}>
        {text}
      </Button>
    );

  return (
    <>
      <Button variant={variant} icon={<FilePlus2 className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        {label}
      </Button>
      <Modal open={open} title={"New quote for…"} onCancel={() => setOpen(false)} footer={null} width={480}>
          <label className="flex items-center gap-2 border-b border-rule-strong pb-1.5 focus-within:border-hema">
            <Search className="size-4 text-ink-3" aria-hidden />
            <input suppressHydrationWarning
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Type a customer's name"
              aria-label="Find a customer"
              autoFocus
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>
          {customers.length === 0 && !typed ? (
            <div className="space-y-3 py-6 text-center">
              <p className="text-meta text-ink-3">You have no customers yet. Add the first one here, and their quote opens next.</p>
              {addButton("Add a customer")}
            </div>
          ) : shown.length === 0 ? (
            <div className="space-y-3 py-6 text-center">
              <p className="text-meta text-ink-3">No customer called &ldquo;{typed}&rdquo; yet.</p>
              {addButton(`Add “${typed}” as a customer`) || <p className="text-meta text-ink-3">Ask someone who can add customers to add them.</p>}
            </div>
          ) : (
            <ul className="mt-2 max-h-80 overflow-y-auto">
              {shown.map((c) => (
                <li key={c.id}>
                  <button suppressHydrationWarning
                    type="button"
                    onClick={() => {
                      setOpen(false);
                      router.push(`/crm/customers/${c.id}/quotes/new`);
                    }}
                    className="w-full rounded-lg px-2 py-2 text-left text-sm hover:bg-hema-tint hover:text-ink"
                  >
                    {c.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {shown.length > 0 && typed && mayAdd && (
            <button suppressHydrationWarning type="button" onClick={addNew} className="mt-2 flex w-full items-center gap-2 rounded-lg border-t border-rule px-2 pt-3 pb-1 text-left text-sm text-ink hover:underline">
              <UserPlus className="size-4" aria-hidden />
              Not in the list? Add &ldquo;{typed}&rdquo; as a new customer
            </button>
          )}
      </Modal>
      <QuickAddWindow open={adding} title="New customer" onClose={() => setAdding(false)}>
        {(done) => <AddCustomer initialName={typed} onAdded={quoteFor} done={done} />}
      </QuickAddWindow>
    </>
  );
}
