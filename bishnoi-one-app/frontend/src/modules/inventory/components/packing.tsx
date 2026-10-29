"use client";

import { Modal } from "antd";
import { Boxes, Check, PackagePlus, Printer, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { deleteWave, makeWave, packDelivery, unpackDelivery, waveStep } from "@/src/modules/inventory/actions/inventory";
import type { Packing } from "@/src/modules/inventory/lib/types";
import { Button } from "@/src/platform/ui/button";
import { CellInput, Field, FormError, Input } from "@/src/platform/ui/field";

// Packages and wave picking (feature plan step 14d): pick → pack → ship.

/** A delivery's boxes: pack everything left in one go, or choose what goes in this box; print the labels. */
export function PackingCard({ orderId, packing, canPack }: { orderId: string; packing: Packing; canPack: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [open, setOpen] = useState(false);
  const left = packing.lines.map((l) => ({ ...l, left: l.quantity - l.packed })).filter((l) => l.left > 0);
  const [qty, setQty] = useState<Record<string, string>>({});
  const [weight, setWeight] = useState("");
  const [error, setError] = useState<string | null>(null);

  function pack(lines: { lineId: string; quantity: number }[]) {
    start(async () => {
      const r = await packDelivery(orderId, { lines, weightKg: Number(weight) || null });
      if (!r.ok) return setError(r.error);
      toast.success(lines.length ? "Box packed" : "Everything left packed in one box");
      setOpen(false);
      setQty({});
      setWeight("");
      setError(null);
      router.refresh();
    });
  }

  function unpack(id: string, number: string) {
    start(async () => {
      const r = await unpackDelivery(orderId, id);
      if (!r.ok) return void toast.error(r.error);
      toast.success(`${number} unpacked`);
      router.refresh();
    });
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <p className="flex-1 text-caps text-ink-3 uppercase">
          <Boxes className="mr-1.5 inline size-4" aria-hidden />
          Packages{packing.packages.length > 0 && ` · ${packing.packages.length}`}
        </p>
        {packing.packages.length > 0 && (
          <Link href={`/inventory/print/orders/${orderId}/labels`} className="inline-flex items-center gap-1.5 text-sm text-hema hover:underline">
            <Printer className="size-4" aria-hidden /> Print labels
          </Link>
        )}
        {canPack && left.length > 0 && (
          <>
            <Button size="sm" icon={<PackagePlus className="size-4" aria-hidden />} loading={busy} onClick={() => pack([])}>
              Pack everything left
            </Button>
            <Button size="sm" variant="quiet" disabled={busy} onClick={() => setOpen(true)}>
              Choose what goes in a box
            </Button>
          </>
        )}
      </div>
      {packing.packages.length === 0 ? (
        <p className="mt-1 text-meta text-ink-3">Not packed yet.</p>
      ) : (
        <ul className="mt-2 divide-y divide-rule text-sm">
          {packing.packages.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-3 py-1.5">
              <span className="font-mono font-semibold">{p.number}</span>
              <span className="text-meta text-ink-3">Box {p.index} of {p.of}{p.weightGrams ? ` · ${(p.weightGrams / 1000).toLocaleString()} kg` : ""}</span>
              <span className="min-w-0 flex-1 truncate text-ink-2">{p.lines.map((l) => `${l.quantity} × ${l.product.name}`).join(", ")}</span>
              {canPack && (
                <button suppressHydrationWarning type="button" title={`Unpack ${p.number}`} disabled={busy} onClick={() => unpack(p.id, p.number)} className="rounded-md p-1 text-ink-3 hover:text-danger">
                  <Trash2 className="size-4" aria-hidden />
                  <span className="sr-only">Unpack {p.number}</span>
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {packing.allPacked && packing.packages.length > 0 && (
        <p className="mt-1 flex items-center gap-1 text-meta text-sage-deep"><Check className="size-3.5" aria-hidden /> Everything is packed</p>
      )}
      <Modal
        open={open}
        title="Pack a box"
        onCancel={() => !busy && setOpen(false)}
        onOk={() => pack(left.map((l) => ({ lineId: l.lineId, quantity: Number(qty[l.lineId]) || 0 })).filter((l) => l.quantity > 0))}
        okText="Pack box"
        confirmLoading={busy}
        destroyOnHidden
      >
        <div className="space-y-3 pt-2">
          {left.map((l) => (
            <div key={l.lineId} className="flex items-center gap-3">
              <span className="min-w-0 flex-1 text-sm">
                {l.product.name} <span className="text-meta text-ink-3">{l.left} left</span>
              </span>
              <CellInput aria-label={`How many ${l.product.name}`} inputMode="numeric" className="w-24 text-right" value={qty[l.lineId] ?? ""} onChange={(e) => setQty({ ...qty, [l.lineId]: e.target.value })} />
            </div>
          ))}
          <Field label="Weight" optional hint="In kilograms.">{(p) => <Input {...p} inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} />}</Field>
          <FormError message={error} />
        </div>
      </Modal>
    </div>
  );
}

/** Pick several held deliveries together. */
export function NewWave({ orders }: { orders: { id: string; number: string; recipient: string; warehouse: string; units: number }[] }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [chosen, setChosen] = useState<string[]>([]);
  const warehouse = orders.find((o) => o.id === chosen[0])?.warehouse;

  function make() {
    start(async () => {
      const r = await makeWave(chosen);
      if (!r.ok) return void toast.error(r.error);
      toast.success(`${r.data.number} started`, { description: "Its deliveries are being picked." });
      router.push(`/inventory/waves/${r.data.id}`);
    });
  }

  if (orders.length === 0) return <p className="text-meta text-ink-3">No deliveries waiting to be picked: confirm deliveries first, so their stock is held.</p>;
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-ink">Deliveries waiting to be picked</p>
      <ul className="divide-y divide-rule text-sm">
        {orders.map((o) => {
          const other = warehouse !== undefined && o.warehouse !== warehouse;
          return (
            <li key={o.id} className="py-1.5">
              <label className={`flex items-center gap-3 ${other ? "opacity-50" : ""}`}>
                <input suppressHydrationWarning type="checkbox" disabled={other} checked={chosen.includes(o.id)} onChange={(e) => setChosen(e.target.checked ? [...chosen, o.id] : chosen.filter((x) => x !== o.id))} className="size-4" />
                <span className="font-mono font-semibold">{o.number}</span>
                <span className="min-w-0 flex-1 truncate">{o.recipient}</span>
                <span className="text-meta text-ink-3">{o.warehouse} · {o.units} units</span>
              </label>
            </li>
          );
        })}
      </ul>
      <Button className="mt-3" variant="primary" loading={busy} disabled={chosen.length === 0} onClick={make}>
        Pick {chosen.length || ""} together
      </Button>
    </div>
  );
}

/** A wave's steps: done, take a delivery out, or let the wave go. */
export function WaveSteps({ waveId, open, orders }: { waveId: string; open: boolean; orders: { id: string; number: string }[] }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  function run(task: () => Promise<{ ok: boolean; error?: string }>, done: string, go?: string) {
    start(async () => {
      const r = await task();
      if (!r.ok) return void toast.error(r.error ?? "That didn't work.");
      toast.success(done);
      if (go) router.push(go);
      else router.refresh();
    });
  }
  if (!open) return null;
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="primary" icon={<Check className="size-4" aria-hidden />} loading={busy} onClick={() => run(() => waveStep(waveId, "done"), "Wave picked: issue its deliveries")}>
        Picked
      </Button>
      {orders.length > 1 &&
        orders.map((o) => (
          <Button key={o.id} size="sm" variant="quiet" disabled={busy} onClick={() => run(() => waveStep(waveId, "remove", o.id), `${o.number} taken out`)}>
            Take out {o.number}
          </Button>
        ))}
      <Button variant="quiet" disabled={busy} onClick={() => run(() => deleteWave(waveId), "Wave let go", "/inventory/waves")}>
        Let go of the wave
      </Button>
    </div>
  );
}
