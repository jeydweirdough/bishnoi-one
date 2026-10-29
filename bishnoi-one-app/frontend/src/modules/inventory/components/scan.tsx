"use client";

import { Check, CircleAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { countScan, scanCode, type Scanned } from "@/src/modules/inventory/actions/inventory";
import { Scanner } from "@/src/platform/ui/scanner";

// Scanning in Inventory (feature plan step 14c), with the shared Scanner box: look anything up, count by
// scanning, and check a delivery's picking against its lines.

const KIND: Record<string, string> = { product: "Item", batch: "Batch", serial: "Serial number", document: "Document" };

/** Scan anything: what it is, and a link to it. A document opens straight away. */
export function ScanLookup() {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [seen, setSeen] = useState<Scanned[]>([]);

  function look(code: string) {
    start(async () => {
      const r = await scanCode(code);
      if (!r.ok) return void toast.error(r.error);
      setSeen((s) => [r.data, ...s].slice(0, 20));
      if (r.data.kind === "document" && r.data.href) router.push(r.data.href);
    });
  }

  return (
    <div className="space-y-4">
      <Scanner onCode={look} busy={busy} label="Scan an item, batch, serial number or document" />
      {seen.length > 0 && (
        <ul className="divide-y divide-rule">
          {seen.map((x, i) => (
            <li key={`${x.code}-${i}`} className="flex flex-wrap items-center gap-3 py-2 text-sm">
              <span className="w-28 shrink-0 text-meta text-ink-3">{KIND[x.kind] ?? "Not found"}</span>
              <span className="min-w-0 flex-1">
                {x.kind === "unknown" ? (
                  <span className="text-ink-2">Nothing has the code <span className="font-mono">{x.code}</span>. Add it as the item&apos;s barcode on the item&apos;s page.</span>
                ) : x.kind === "batches" ? (
                  <span className="text-ink-2">
                    Batch {x.code} is on several items:{" "}
                    {x.batches?.map((b, k) => (
                      <Link key={b.id} href={`/inventory/products/${b.product.id}/batches`} className="text-hema hover:underline">
                        {k > 0 && ", "}{b.product.name}
                      </Link>
                    ))}
                  </span>
                ) : (
                  <Link href={x.href ?? "#"} className="font-medium text-ink hover:underline">
                    {x.document ? `${x.document.label} ${x.document.number}` : x.product?.name}
                    {x.batch && <span className="text-ink-3"> · batch {x.batch.batchNo}</span>}
                    {x.serial && <span className="text-ink-3"> · serial {x.serial}</span>}
                  </Link>
                )}
              </span>
              <span className="font-mono text-meta text-ink-3">{x.code}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Count by scanning: each scan adds one (several people can scan into the same count). */
export function CountByScan({ countId }: { countId: string }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [last, setLast] = useState<{ name: string; counted: number; expected: number; isNew: boolean } | null>(null);

  function count(code: string) {
    start(async () => {
      const r = await countScan(countId, code);
      if (!r.ok) return void toast.error(r.error);
      setLast({ name: r.data.product.name + (r.data.batch ? ` · ${r.data.batch.batchNo}` : ""), counted: r.data.counted, expected: r.data.expected, isNew: r.data.new });
      router.refresh();
    });
  }

  return (
    <div className="space-y-2">
      <Scanner onCode={count} busy={busy} label="Scan an item or batch to count it" />
      {last && (
        <p className="text-sm text-ink" aria-live="polite">
          <strong>{last.name}</strong>: {last.counted} counted of {last.expected} expected
          {last.isNew && <span className="text-ink-3"> (not expected here: added)</span>}
        </p>
      )}
    </div>
  );
}

type PickLine = { id: string; productId: string; name: string; sku: string; quantity: number };

/** Check picking by scanning: each line ticks off as its quantity is scanned; a wrong item or one too many says so.
 *  Only a check on screen: issuing is still the Issue button. */
export function PickCheck({ lines }: { lines: PickLine[] }) {
  const [busy, start] = useTransition();
  const [picked, setPicked] = useState<Record<string, number>>({});
  const [warning, setWarning] = useState<string | null>(null);
  const done = lines.every((l) => (picked[l.id] ?? 0) >= l.quantity);

  function pick(code: string) {
    start(async () => {
      const r = await scanCode(code);
      if (!r.ok) return void toast.error(r.error);
      const id = r.data.product?.id;
      const line = id ? lines.find((l) => l.productId === id) : undefined;
      if (!line) return setWarning(id ? `${r.data.product?.name} isn't on this delivery.` : `Nothing has the code ${code}.`);
      const now = picked[line.id] ?? 0;
      const add = r.data.pack?.quantity ?? 1;
      if (now >= line.quantity) return setWarning(`All ${line.quantity} of ${line.name} are already picked.`);
      if (now + add > line.quantity) return setWarning(`A ${r.data.pack?.name} holds ${add}: only ${line.quantity - now} more of ${line.name} are needed.`);
      setWarning(null);
      setPicked((p) => ({ ...p, [line.id]: now + add }));
    });
  }

  return (
    <div className="space-y-3">
      <Scanner onCode={pick} busy={busy} label="Scan each item as you pick it" autoFocus={false} />
      {warning && (
        <p className="flex items-center gap-1.5 text-sm text-danger" role="alert">
          <CircleAlert className="size-4" aria-hidden /> {warning}
        </p>
      )}
      <ul className="divide-y divide-rule text-sm">
        {lines.map((l) => {
          const n = picked[l.id] ?? 0;
          return (
            <li key={l.id} className="flex items-center gap-3 py-1.5">
              <span className="min-w-0 flex-1">
                {l.name} <span className="text-meta text-ink-3">{l.sku}</span>
              </span>
              <span className={`tabular-nums ${n >= l.quantity ? "font-semibold text-sage-deep" : "text-ink-2"}`}>
                {n} / {l.quantity}
              </span>
              {n >= l.quantity && <Check className="size-4 text-sage-deep" aria-hidden />}
            </li>
          );
        })}
      </ul>
      {done && <p className="text-sm font-medium text-sage-deep">Everything is picked. Issue the delivery when it&apos;s packed.</p>}
    </div>
  );
}
