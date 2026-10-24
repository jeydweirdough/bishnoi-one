"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/modules/pharmacy/platform/ui/button";
import { Choice, Field, FormError, Input, Select } from "@/src/modules/pharmacy/platform/ui/field";
import { adjustStock } from "@/src/modules/pharmacy/actions/pharmacy";

type BatchOption = { id: string; label: string; qtyOnHand: number; unit: string };

const REASONS = ["Recount", "Damaged", "Expired: taken off the shelf", "Recalled: sent back", "Found"];

/** Correcting one batch by the difference counted, with the reason. */
export function AdjustForm({ batches, preset }: { batches: BatchOption[]; preset?: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [batchId, setBatchId] = useState(preset ?? "");
  const [way, setWay] = useState<"out" | "in">("out");
  const [qty, setQty] = useState("");
  const [reason, setReason] = useState(preset ? REASONS[2] : "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const batch = batches.find((b) => b.id === batchId);

  function submit() {
    const n = Number.parseInt(qty, 10) || 0;
    start(async () => {
      const result = await adjustStock(batchId, way === "out" ? -n : n, reason.trim());
      if (result.ok) {
        toast.success("Stock adjusted", { description: `${result.data.medicine.label}, lot ${result.data.batch.lotNo}: ${result.data.balance} left` });
        router.push("/pharmacy/stock?view=adjustment");
        router.refresh();
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-6"
    >
      <Field label="Batch" error={fields.batchId}>
        {(p) => (
          <Select {...p} value={batchId} onChange={(e) => setBatchId(e.target.value)}>
            <option value="">Pick a batch</option>
            {batches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.label} · {b.qtyOnHand} on hand
              </option>
            ))}
          </Select>
        )}
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Choice
          name="way"
          legend="Which way"
          value={way}
          onChange={setWay}
          options={[
            { value: "out", label: "Take off" },
            { value: "in", label: "Add back" },
          ]}
        />
        <Field
          label={`How many${batch ? ` (${batch.unit})` : ""}`}
          error={fields.quantity}
          hint={batch && way === "out" ? `${batch.qtyOnHand} on hand; taking all leaves it empty.` : undefined}
        >
          {(p) => <Input {...p} inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value.replace(/\D/g, ""))} />}
        </Field>
      </div>
      <Field label="Reason" error={fields.reason} hint="Kept with the movement, so the count can always be explained.">
        {(p) => (
          <>
            <Input {...p} list="adjust-reasons" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} />
            <datalist id="adjust-reasons">
              {REASONS.map((r) => (
                <option key={r} value={r} />
              ))}
            </datalist>
          </>
        )}
      </Field>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending} disabled={!batchId || !qty}>
          {way === "out" ? "Take off stock" : "Add stock back"}
        </Button>
        <LinkButton href="/pharmacy/stock?view=adjustment" variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
