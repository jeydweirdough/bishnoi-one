"use client";

import { Check, ClipboardCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { finishQualityCheck, saveWarehouse } from "@/src/modules/inventory/actions/inventory";
import type { QualityCheck } from "@/src/modules/inventory/lib/types";
import { Button } from "@/src/platform/ui/button";
import { CellInput, FormError, Select, Textarea } from "@/src/platform/ui/field";

// Quality checks on receipt (feature plan step 14a): receive → check → store. What arrives waits on hold;
// the checker says how many passed and failed (with why); passed is released, failed put aside as damaged.

/** The check, line by line: passed defaults to everything received; failed needs a reason. */
export function QualityCheckForm({ check }: { check: QualityCheck }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [rows, setRows] = useState(() =>
    Object.fromEntries(check.lines.map((l) => [l.id, { passed: String(l.quantity), failed: "0", reason: "", note: "" }])),
  );
  const [notes, setNotes] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function set(id: string, key: "passed" | "failed" | "reason" | "note", value: string, quantity: number) {
    setRows((r) => {
      const row = { ...r[id], [key]: value };
      // Keep the two adding up to what arrived: typing one fills the other.
      if (key === "failed") row.passed = String(Math.max(0, quantity - (Number(value) || 0)));
      if (key === "passed") row.failed = String(Math.max(0, quantity - (Number(value) || 0)));
      return { ...r, [id]: row };
    });
  }

  function submit() {
    start(async () => {
      const r = await finishQualityCheck(check.id, {
        notes: notes.trim() || null,
        lines: check.lines.map((l) => ({
          lineId: l.id, passed: Number(rows[l.id].passed) || 0, failed: Number(rows[l.id].failed) || 0,
          reason: Number(rows[l.id].failed) > 0 ? rows[l.id].reason || null : null, note: rows[l.id].note.trim() || null,
        })),
      });
      if (!r.ok) {
        setFields(r.fields ?? {});
        return setError(r.fields ? "Check the lines marked." : r.error);
      }
      toast.success(`${check.number} done`, { description: "What passed can be used now; what failed is set aside as damaged." });
      router.refresh();
    });
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[48rem] text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-meta text-ink-3">
              <th className="py-2 pr-3 font-medium">Product</th>
              <th className="py-2 pr-3 text-right font-medium">Received</th>
              <th className="py-2 pr-3 text-right font-medium">Passed</th>
              <th className="py-2 pr-3 text-right font-medium">Failed</th>
              <th className="py-2 pr-3 font-medium">Why it failed</th>
              <th className="py-2 font-medium">Note</th>
            </tr>
          </thead>
          <tbody>
            {check.lines.map((l, i) => {
              const row = rows[l.id];
              const failing = Number(row.failed) > 0;
              return (
                <tr key={l.id} className="border-b border-rule align-top">
                  <td className="py-2 pr-3">
                    <span className="font-medium text-ink">{l.product.name}</span>
                    <span className="block text-meta text-ink-3">
                      {l.product.sku} · {l.location.code}
                      {l.batch && ` · batch ${l.batch.batchNo}`}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{l.quantity}</td>
                  <td className="w-24 py-2 pr-3">
                    <CellInput aria-label={`Passed, ${l.product.name}`} inputMode="numeric" value={row.passed} onChange={(e) => set(l.id, "passed", e.target.value, l.quantity)} className="text-right" />
                    {fields[`lines.${i}.passed`] && <span className="block text-meta text-danger">{fields[`lines.${i}.passed`]}</span>}
                  </td>
                  <td className="w-24 py-2 pr-3">
                    <CellInput aria-label={`Failed, ${l.product.name}`} inputMode="numeric" value={row.failed} onChange={(e) => set(l.id, "failed", e.target.value, l.quantity)} className="text-right" />
                  </td>
                  <td className="w-48 py-2 pr-3">
                    {failing && (
                      <Select aria-label={`Why ${l.product.name} failed`} value={row.reason} onChange={(e) => set(l.id, "reason", e.target.value, l.quantity)} placeholder="Pick why">
                        {check.reasons.map((r) => (
                          <option key={r.value} value={r.value}>{r.label}</option>
                        ))}
                      </Select>
                    )}
                    {fields[`lines.${i}.reason`] && <span className="block text-meta text-danger">{fields[`lines.${i}.reason`]}</span>}
                  </td>
                  <td className="py-2">
                    <CellInput aria-label={`Note, ${l.product.name}`} value={row.note} onChange={(e) => set(l.id, "note", e.target.value, l.quantity)} maxLength={300} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Textarea aria-label="Notes" rows={2} placeholder="Notes for the whole delivery (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} />
      <FormError message={error} />
      <Button variant="primary" icon={<Check className="size-4" aria-hidden />} loading={busy} onClick={submit}>
        Finish check
      </Button>
    </div>
  );
}

/** Whether a warehouse checks what it receives before it can be used (receive → check → store). */
export function QualityCheckSwitch({ warehouseId, on }: { warehouseId: string; on: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  return (
    <Button
      size="sm"
      variant="quiet"
      icon={<ClipboardCheck className="size-4" aria-hidden />}
      loading={busy}
      onClick={() =>
        start(async () => {
          const r = await saveWarehouse(warehouseId, { qualityCheck: !on });
          if (!r.ok) return void toast.error(r.error);
          toast.success(on ? "Goods received here are usable at once" : "Goods received here wait for a quality check");
          router.refresh();
        })
      }
    >
      {on ? "Stop checking goods on arrival" : "Check goods on arrival"}
    </Button>
  );
}
