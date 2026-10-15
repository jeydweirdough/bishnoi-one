"use client";

import { Paperclip } from "lucide-react";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";
import { askToDistribute, crmTeams, orderProduction, type CrmTeam, type Material, type MaterialPage } from "@/src/actions/materials";
import { FormField, ModalFrame, inputClass } from "@/src/components/executive-modals";
import { Button } from "@/src/platform/ui/button";

const today = () => new Date().toLocaleDateString("en-CA");

function Errors({ error }: { error: string | null }) {
  return error ? (
    <p role="alert" className="rounded-[14px] bg-danger-tint px-3 py-2 text-meta text-danger">
      {error}
    </p>
  ) : null;
}

function Hint({ error, hint }: { error?: string; hint?: string }) {
  if (error) return <p className="mt-1 text-meta text-danger">{error}</p>;
  return hint ? <p className="mt-1 text-meta text-ink-3">{hint}</p> : null;
}

function Footer({ onClose, pending, label }: { onClose: () => void; pending: boolean; label: string }) {
  return (
    <div className="flex justify-end gap-2 border-t border-rule pt-4">
      <Button variant="quiet" onClick={onClose}>
        Cancel
      </Button>
      <Button variant="primary" type="submit" disabled={pending}>
        {pending ? "Saving…" : label}
      </Button>
    </div>
  );
}

/** A print run or order of the approved design, by the executive office. */
export function ProductionDialog({ material, onClose, onDone }: { material: Material; onClose: () => void; onDone: (page: MaterialPage) => void }) {
  // Starts from what marketing planned: the quantity and the budget.
  const [v, setV] = useState({
    quantity: material.quantity ? String(material.quantity) : "",
    supplier: "",
    cost: material.budget != null ? String(material.budget) : "",
    orderedOn: today(),
    expectedOn: material.neededBy ?? "",
    notes: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const set = (key: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [key]: e.target.value });

  function save() {
    const quantity = Number(v.quantity.replace(/,/g, ""));
    if (!Number.isInteger(quantity) || quantity < 1) return setErrors({ quantity: "Say how many are being produced." });
    start(async () => {
      const r = await orderProduction(material.id, {
        quantity,
        supplier: v.supplier.trim() || null,
        cost: v.cost.trim() ? Number(v.cost.replace(/,/g, "")) : null,
        orderedOn: v.orderedOn || null,
        expectedOn: v.expectedOn || null,
        notes: v.notes.trim() || null,
      });
      if (!r.ok) {
        setErrors(r.fields ?? {});
        setError(r.fields ? null : r.error);
        return;
      }
      toast.success("Production ordered", { description: `${quantity.toLocaleString()} × ${material.title}` });
      onDone(r.data);
      onClose();
    });
  }

  return (
    <ModalFrame title="Order production" subtitle={`${material.title} · the design the pharmacist approved`} onClose={onClose}>
      <form noValidate onSubmit={(e) => (e.preventDefault(), save())} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <FormField label="Quantity">
              <input value={v.quantity} onChange={set("quantity")} inputMode="numeric" placeholder="e.g. 500" aria-invalid={errors.quantity ? true : undefined} className={inputClass} />
            </FormField>
            <Hint error={errors.quantity} />
          </div>
          <div>
            <FormField label="Supplier" optional>
              <input value={v.supplier} onChange={set("supplier")} maxLength={160} placeholder="The printer or maker" className={inputClass} />
            </FormField>
          </div>
          <div>
            <FormField label="Total cost" optional>
              <input value={v.cost} onChange={set("cost")} inputMode="decimal" placeholder="₱" aria-invalid={errors.cost ? true : undefined} className={inputClass} />
            </FormField>
            <Hint error={errors.cost} />
          </div>
          <div>
            <FormField label="Date ordered">
              <input type="date" value={v.orderedOn} onChange={set("orderedOn")} className={inputClass} />
            </FormField>
          </div>
          <div>
            <FormField label="Expected delivery" optional>
              <input type="date" value={v.expectedOn} onChange={set("expectedOn")} className={inputClass} />
            </FormField>
          </div>
          <div className="sm:col-span-2">
            <FormField label="Notes" optional>
              <textarea value={v.notes} onChange={set("notes")} rows={2} maxLength={500} className={inputClass} />
            </FormField>
          </div>
        </div>
        <Errors error={error} />
        <Footer onClose={onClose} pending={pending} label="Order production" />
      </form>
    </ModalFrame>
  );
}

/** A request to give some to a CRM team, or one person in it: their manager approves it in the CRM. */
export function DistributionDialog({ material, onClose, onDone }: { material: Material; onClose: () => void; onDone: (page: MaterialPage) => void }) {
  const [teams, setTeams] = useState<CrmTeam[] | null>(null);
  const [v, setV] = useState({ teamId: "", recipientId: "", quantity: "", purpose: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const team = teams?.find((t) => t.id === v.teamId);

  useEffect(() => {
    crmTeams().then((r) => {
      if (r.ok) setTeams(r.data);
      else setError(r.error);
    });
  }, []);

  function save() {
    const quantity = Number(v.quantity.replace(/,/g, ""));
    const wrong: Record<string, string> = {};
    if (!v.teamId) wrong.teamId = "Pick the team.";
    if (!Number.isInteger(quantity) || quantity < 1) wrong.quantity = "Say how many.";
    else if (quantity > material.available) wrong.quantity = `Only ${material.available.toLocaleString()} are free to give out.`;
    if (Object.keys(wrong).length) return setErrors(wrong);
    start(async () => {
      const r = await askToDistribute(material.id, { teamId: v.teamId, recipientId: v.recipientId || null, quantity, purpose: v.purpose.trim() || null });
      if (!r.ok) {
        setErrors(r.fields ?? {});
        setError(r.fields ? null : r.error);
        return;
      }
      toast.success("Sent for the manager's approval", { description: `${quantity.toLocaleString()} for ${team?.name ?? "the team"}` });
      onDone(r.data);
      onClose();
    });
  }

  return (
    <ModalFrame title="Request distribution" subtitle={`${material.title} · ${material.available.toLocaleString()} free to give out`} onClose={onClose}>
      <form noValidate onSubmit={(e) => (e.preventDefault(), save())} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <FormField label="Team">
              <select
                value={v.teamId}
                onChange={(e) => setV({ ...v, teamId: e.target.value, recipientId: "" })}
                disabled={!teams}
                aria-invalid={errors.teamId ? true : undefined}
                className={inputClass}
              >
                <option value="">{teams ? "Pick a team" : "Loading the CRM's teams…"}</option>
                {teams?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </FormField>
            <Hint error={errors.teamId} hint={team ? (team.manager ? `Approved by ${team.manager.name}, its manager.` : "No manager set: the CRM's administrator approves.") : undefined} />
          </div>
          <div>
            <FormField label="Recipient" optional>
              <select value={v.recipientId} onChange={(e) => setV({ ...v, recipientId: e.target.value })} disabled={!team} aria-invalid={errors.recipientId ? true : undefined} className={inputClass}>
                <option value="">The whole team</option>
                {team?.people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </FormField>
            <Hint error={errors.recipientId} />
          </div>
          <div>
            <FormField label="Quantity">
              <input value={v.quantity} onChange={(e) => setV({ ...v, quantity: e.target.value })} inputMode="numeric" aria-invalid={errors.quantity ? true : undefined} className={inputClass} />
            </FormField>
            <Hint error={errors.quantity} />
          </div>
          <div className="sm:col-span-2">
            <FormField label="Purpose" optional>
              <textarea value={v.purpose} onChange={(e) => setV({ ...v, purpose: e.target.value })} rows={2} maxLength={500} placeholder="e.g. Doctor visits in October" className={inputClass} />
            </FormField>
          </div>
        </div>
        <Errors error={error} />
        <Footer onClose={onClose} pending={pending} label="Submit for approval" />
      </form>
    </ModalFrame>
  );
}

/**
 * A step that happened (received, given out): its date, today unless it was
 * earlier, and a photo or scan as proof (the delivery, the signed receipt).
 */
export function DateDialog({
  title,
  subtitle,
  label,
  proofHint,
  confirm,
  onClose,
  onSave,
}: {
  title: string;
  subtitle: string;
  label: string;
  proofHint: string;
  confirm: string;
  onClose: () => void;
  onSave: (form: FormData) => Promise<string | null>;
}) {
  const [on, setOn] = useState(today());
  const [proof, setProof] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <ModalFrame title={title} subtitle={subtitle} onClose={onClose}>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          if (proof && proof.size > 3 * 1024 * 1024) return setError("The proof is over 3 MB. Take a smaller photo or scan.");
          const form = new FormData();
          form.set("on", on);
          if (proof) form.set("proof", proof, proof.name);
          start(async () => {
            const problem = await onSave(form);
            if (problem) setError(problem);
            else onClose();
          });
        }}
        className="space-y-5"
      >
        <FormField label={label}>
          <input type="date" value={on} max={today()} onChange={(e) => setOn(e.target.value)} className={inputClass} />
        </FormField>
        <div>
          <FormField label="Proof" optional>
            <label className="flex cursor-pointer items-center gap-3 rounded-[14px] border border-dashed border-rule-strong px-3.5 py-3 text-sm text-ink-2 hover:border-ink">
              <Paperclip className="size-4 shrink-0" aria-hidden />
              <span className="min-w-0 flex-1 truncate">{proof ? proof.name : "Attach a photo (PNG or JPG) or a PDF, up to 3 MB"}</span>
              <input type="file" accept="image/png,image/jpeg,application/pdf" capture="environment" className="sr-only" onChange={(e) => setProof(e.target.files?.[0] ?? null)} />
            </label>
          </FormField>
          <p className="mt-1 text-meta text-ink-3">{proofHint}</p>
        </div>
        <Errors error={error} />
        <Footer onClose={onClose} pending={pending} label={confirm} />
      </form>
    </ModalFrame>
  );
}
