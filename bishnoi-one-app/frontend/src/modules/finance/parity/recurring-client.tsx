"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/modules/finance/platform/ui/field";
import { screen } from "@/src/modules/finance/lib/links";
import { createRecurring, deleteRecurring, generateRecurringNow, runDueRecurring, toggleRecurring } from "./actions";
import type { RecurringItem } from "./types";

type Option = { id: string; name: string; code?: string };

function toCentavos(v: string): number {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? Math.round(n * 100) : 0;
}

export function RecurringClient({
  today,
  items,
  dueCount,
  suppliers,
  accounts,
  incomeAccounts,
  canCreate,
}: {
  today: string;
  items: RecurringItem[];
  dueCount: number;
  suppliers: Option[];
  accounts: Option[];
  incomeAccounts: Option[];
  canCreate: boolean;
}) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<"bill" | "invoice">("bill");
  const [name, setName] = useState("");
  const [frequency, setFrequency] = useState("monthly");
  const [startDate, setStartDate] = useState(today);
  const [supplierId, setSupplierId] = useState(suppliers[0]?.id ?? "");
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [customerName, setCustomerName] = useState("");
  const [incomeAccountId, setIncomeAccountId] = useState(incomeAccounts[0]?.id ?? "");
  const [amountPesos, setAmountPesos] = useState("");
  const [vat, setVat] = useState("vat");
  const [recentGenerated, setRecentGenerated] = useState<{ kind: string; id: string; href: string; label: string }[]>([]);

  function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const amountCentavos = toCentavos(amountPesos);
    if (!name.trim() || amountCentavos <= 0) {
      setError("Enter a schedule name and positive amount.");
      return;
    }
    const payload =
      kind === "bill"
        ? {
            supplierId,
            billNumberPrefix: name.trim().slice(0, 12).toUpperCase().replace(/[^A-Z0-9]+/g, "-"),
            amountsIncludeVat: true,
            lines: [{ accountId, description: name.trim(), amountCentavos, vat, purchaseType: "services" }],
          }
        : {
            customerName: customerName.trim(),
            termsDays: 30,
            lines: [{ accountId: incomeAccountId || null, description: name.trim(), quantity: 1, unitPriceCentavos: amountCentavos }],
          };
    start(async () => {
      const res = await createRecurring({ kind, name: name.trim(), frequency, startDate, payload });
      if (!res.ok) return setError(res.error);
      toast.success("Recurring schedule created");
      setName("");
      setAmountPesos("");
    });
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-rule bg-bench px-4 py-3 text-meta text-ink-2">
        <strong className="text-ink">How Recurring Schedules work:</strong> Set up rent, utilities, or monthly retainers once.
        {" "}When due, click <strong>Run all due schedules</strong> (or <strong>Generate draft</strong>) to create a Draft bill or invoice — nothing posts or pays until staff review tax and approve.
      </div>
      {canCreate && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rule bg-bench px-4 py-3">
          <div>
            <div className="text-sm font-medium text-ink">
              {dueCount} {dueCount === 1 ? "schedule is" : "schedules are"} due today ({today})
            </div>
            <p className="text-meta text-ink-2">Running creates standard Draft bills/invoices so staff review tax &amp; approve before posting.</p>
          </div>
          <Button
            variant="primary"
            loading={pending}
            disabled={dueCount === 0}
            onClick={() =>
              start(async () => {
                const r = await runDueRecurring();
                if (!r.ok) toast.error(r.error);
                else {
                  toast.success(`Generated ${r.data.count} draft(s)`);
                  setRecentGenerated(r.data.generated);
                }
              })
            }
          >
            Run all due schedules
          </Button>
        </div>
      )}

      {recentGenerated.length > 0 && (
        <div className="rounded-lg border border-rule bg-sheet p-4 space-y-2">
          <div className="text-meta font-semibold text-ink">Drafts generated just now</div>
          <ul className="space-y-1 text-sm">
            {recentGenerated.map((g) => (
              <li key={g.id}>
                <Link href={screen(g.href)} className="text-ink underline hover:text-ink-2">
                  {g.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {canCreate && (
        <form onSubmit={onCreate} className="rounded-lg border border-rule bg-sheet p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-ink">New recurring schedule</h2>
            <div className="flex gap-2">
              <Button type="button" size="sm" variant={kind === "bill" ? "primary" : "default"} onClick={() => setKind("bill")}>
                Recurring bill
              </Button>
              <Button type="button" size="sm" variant={kind === "invoice" ? "primary" : "default"} onClick={() => setKind("invoice")}>
                Recurring invoice
              </Button>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Schedule name">
              {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder="Monthly Warehouse Rent" />}
            </Field>
            <Field label="Frequency">
              {(p) => (
                <Select {...p} value={frequency} onChange={(e) => setFrequency(e.target.value)}>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="yearly">Yearly</option>
                </Select>
              )}
            </Field>
            <Field label="First run date">
              {(p) => <Input {...p} type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />}
            </Field>

            {kind === "bill" ? (
              <>
                <Field label="Supplier">
                  {(p) => (
                    <Select {...p} value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                      <option value="">Pick supplier…</option>
                      {suppliers.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <Field label="Expense / Asset account">
                  {(p) => (
                    <Select {...p} value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                      {accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code ? `${a.code} · ` : ""}
                          {a.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <Field label="VAT">
                  {(p) => (
                    <Select {...p} value={vat} onChange={(e) => setVat(e.target.value)}>
                      <option value="vat">VATable (12%)</option>
                      <option value="zero">Zero-rated</option>
                      <option value="exempt">VAT-exempt</option>
                      <option value="none">Non-VAT</option>
                    </Select>
                  )}
                </Field>
              </>
            ) : (
              <>
                <Field label="Customer name">
                  {(p) => <Input {...p} value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Customer name" />}
                </Field>
                <Field label="Income account" optional>
                  {(p) => (
                    <Select {...p} value={incomeAccountId} onChange={(e) => setIncomeAccountId(e.target.value)}>
                      <option value="">Default sales account</option>
                      {incomeAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code ? `${a.code} · ` : ""}
                          {a.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              </>
            )}
            <Field label="Amount (PHP)">
              {(p) => <Input {...p} type="number" step="0.01" min="0.01" value={amountPesos} onChange={(e) => setAmountPesos(e.target.value)} placeholder="0.00" />}
            </Field>
          </div>
          <FormError message={error} />
          <Button type="submit" variant="primary" loading={pending}>
            Save schedule
          </Button>
        </form>
      )}

      <div className="overflow-x-auto rounded-lg border border-rule bg-sheet">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-rule bg-bench text-meta text-ink-2">
            <tr>
              <th className="px-4 py-3">Schedule</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Frequency</th>
              <th className="px-4 py-3">Next run</th>
              <th className="px-4 py-3 text-right">Generated</th>
              <th className="px-4 py-3">State</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {items.map((t) => (
              <tr key={t.id}>
                <td className="px-4 py-3 font-medium text-ink">{t.name}</td>
                <td className="px-4 py-3 capitalize text-ink-2">{t.kind}</td>
                <td className="px-4 py-3 capitalize text-ink-2">{t.frequency}</td>
                <td className="px-4 py-3 font-mono text-ink-2">
                  {t.nextRunDate}
                  {t.isDue && <span className="ml-2 rounded bg-bench px-1.5 py-0.5 text-meta font-semibold text-ink">Due</span>}
                </td>
                <td className="px-4 py-3 text-right font-mono">{t.generatedCount}</td>
                <td className="px-4 py-3 text-ink-2">{t.isActive ? "Active" : "Paused"}</td>
                <td className="px-4 py-3 text-right space-x-2">
                  {canCreate && (
                    <>
                      <Button
                        size="sm"
                        loading={pending}
                        onClick={() =>
                          start(async () => {
                            const r = await generateRecurringNow(t.id);
                            if (!r.ok) toast.error(r.error);
                            else {
                              toast.success(`Generated ${r.data.label}`);
                              setRecentGenerated((prev) => [r.data, ...prev]);
                            }
                          })
                        }
                      >
                        Generate draft
                      </Button>
                      <Button
                        size="sm"
                        onClick={() =>
                          start(async () => {
                            const r = await toggleRecurring(t.id, !t.isActive);
                            if (!r.ok) toast.error(r.error);
                            else toast.success(t.isActive ? "Paused" : "Resumed");
                          })
                        }
                      >
                        {t.isActive ? "Pause" : "Resume"}
                      </Button>
                      <Button
                        size="sm"
                        onClick={() =>
                          start(async () => {
                            const r = await deleteRecurring(t.id);
                            if (!r.ok) toast.error(r.error);
                            else toast.success("Deleted");
                          })
                        }
                      >
                        Delete
                      </Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-ink-3">
                  No recurring schedules yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
