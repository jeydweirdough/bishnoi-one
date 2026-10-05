"use client";

import { Pencil, Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { Empty } from "@/src/platform/ui/sheet";
import { savePurpose } from "../../actions/funds";
import type { FundPurpose } from "./types";

/** What money can be asked for, and whether each is liquidated. */
export function PurposesEditor({ purposes }: { purposes: FundPurpose[] }) {
  const [editing, setEditing] = useState<FundPurpose | "new" | null>(null);
  return (
    <div className="space-y-4">
      {editing ? (
        <PurposeForm key={editing === "new" ? "new" : editing.id} purpose={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
      ) : (
        <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
          Add a purpose
        </Button>
      )}
      {purposes.length === 0 ? (
        <Empty title="No purposes yet" icon="payments">
          Add the purposes a marketing request can be made for: client meals, transportation.
        </Empty>
      ) : (
        <ul className="divide-y divide-rule">
          {purposes.map((p) => (
            <li key={p.id} className={`flex items-center gap-3 py-2.5 ${p.isActive ? "" : "text-ink-3"}`}>
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1 text-sm font-semibold">
                  {p.name}
                  <Button size="sm" variant="quiet" className="!px-1.5" aria-label={`Change ${p.name}`} onClick={() => setEditing(p)}>
                    <Pencil className="size-3.5" aria-hidden />
                  </Button>
                </p>
                <p className="text-meta text-ink-3">
                  {p.liquidate ? "Subject to liquidation" : "Not subject to liquidation"}
                  {p.description && ` · ${p.description}`}
                  {!p.isActive && " · switched off"}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PurposeForm({ purpose, onDone }: { purpose: FundPurpose | null; onDone: () => void }) {
  const [name, setName] = useState(purpose?.name ?? "");
  const [description, setDescription] = useState(purpose?.description ?? "");
  const [liquidate, setLiquidate] = useState(purpose?.liquidate ?? true);
  const [isActive, setActive] = useState(purpose?.isActive ?? true);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setFields({ name: "Enter a name." });
      return;
    }
    start(async () => {
      const result = await savePurpose(purpose?.id ?? null, { name: name.trim(), description: description.trim() || null, liquidate, isActive });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(purpose ? "Purpose saved" : "Purpose added", { description: result.data.name });
      onDone();
    });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4 rounded-[6px] border border-rule p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Purpose" error={fields.name}>
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder="Client meal" autoFocus />}
        </Field>
        <Field label="Description" optional error={fields.description}>
          {(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} />}
        </Field>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={liquidate} onChange={(e) => setLiquidate(e.target.checked)} className="size-4 accent-hema" />
        Subject to liquidation (expenses and official receipts are submitted after spending)
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={isActive} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-hema" />
        Active (available for new requests)
      </label>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {purpose ? "Save" : "Add purpose"}
        </Button>
        <Button variant="quiet" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
