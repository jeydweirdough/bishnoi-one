"use client";

import { Checkbox } from "antd";
import { ShoppingCart } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { makeReplenishmentDrafts, saveReplenishmentSettings } from "@/src/modules/inventory/actions/inventory";
import type { ReplenishmentSettings } from "@/src/modules/inventory/lib/types";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";

// Replenishment (feature plan step 15a): what to order, from use and lead time; drafts per vendor.

export function MakeDrafts({ warehouseId, due }: { warehouseId: string; due: number }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  if (due === 0) return null;
  return (
    <Button
      variant="primary"
      icon={<ShoppingCart className="size-4" aria-hidden />}
      loading={busy}
      onClick={() =>
        start(async () => {
          const r = await makeReplenishmentDrafts(warehouseId);
          if (!r.ok) return void toast.error(r.error);
          const { made, needVendor } = r.data;
          toast.success(made.length ? `${made.length} draft purchase ${made.length === 1 ? "order" : "orders"} made` : "No drafts made", {
            description: [made.map((m) => `${m.number} (${m.supplier})`).join(", "), needVendor.length ? `${needVendor.length} without a usual vendor: set one on the item.` : ""].filter(Boolean).join(" · ") || undefined,
          });
          router.refresh();
        })
      }
    >
      Make draft purchase orders
    </Button>
  );
}

export function ReplenishmentSettingsForm({ settings, canChange }: { settings: ReplenishmentSettings; canChange: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [form, setForm] = useState({ safetyDays: String(settings.safetyDays), defaultLeadDays: String(settings.defaultLeadDays), historyDays: String(settings.historyDays), automatic: settings.automatic });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function save() {
    start(async () => {
      const r = await saveReplenishmentSettings({ safetyDays: Number(form.safetyDays), defaultLeadDays: Number(form.defaultLeadDays), historyDays: Number(form.historyDays), automatic: form.automatic });
      if (!r.ok) {
        setFields(r.fields ?? {});
        return setError(r.fields ? null : r.error);
      }
      toast.success("Saved");
      setFields({});
      setError(null);
      router.refresh();
    });
  }

  return (
    <form noValidate onSubmit={(e) => (e.preventDefault(), save())} className="grid items-end gap-4 sm:grid-cols-4">
      <Field label="Safety days" hint="Added to every lead time." error={fields.safetyDays}>{(p) => <Input {...p} inputMode="numeric" value={form.safetyDays} disabled={!canChange} onChange={(e) => setForm({ ...form, safetyDays: e.target.value })} />}</Field>
      <Field label="Lead time when the vendor gives none" hint="Days." error={fields.defaultLeadDays}>{(p) => <Input {...p} inputMode="numeric" value={form.defaultLeadDays} disabled={!canChange} onChange={(e) => setForm({ ...form, defaultLeadDays: e.target.value })} />}</Field>
      <Field label="Days of use to average" error={fields.historyDays}>{(p) => <Input {...p} inputMode="numeric" value={form.historyDays} disabled={!canChange} onChange={(e) => setForm({ ...form, historyDays: e.target.value })} />}</Field>
      <div className="pb-2">
        <Checkbox checked={form.automatic} disabled={!canChange} onChange={(e) => setForm({ ...form, automatic: e.target.checked })}>
          Make the drafts by themselves each night
        </Checkbox>
      </div>
      {canChange && (
        <div className="sm:col-span-4">
          <FormError message={error} />
          <Button type="submit" size="sm" loading={busy}>Save settings</Button>
          {settings.lastRunAt && <span className="ml-3 text-meta text-ink-3">Last made {new Date(settings.lastRunAt).toLocaleString()}</span>}
        </div>
      )}
      {!canChange && <p className="text-meta text-ink-3 sm:col-span-4">A purchasing approver changes these. <Link href="/inventory/purchase-orders" className="text-hema hover:underline">Purchase orders</Link></p>}
    </form>
  );
}
