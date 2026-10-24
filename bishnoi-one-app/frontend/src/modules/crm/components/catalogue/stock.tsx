"use client";

import { RefreshCw } from "lucide-react";
import { useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import type { StockLevel } from "@/src/platform/lib/types";
import { syncProducts } from "@/src/modules/crm/actions/catalogue";

// How much Bishnoi One Inventory has of a product, as the Products list and the
// quote form show it.

const STATE: Record<NonNullable<StockLevel["state"]>, { label: string; className: string }> = {
  out: { label: "Out of stock", className: "bg-danger-tint text-danger" },
  low: { label: "Low", className: "bg-[#fdf3e1] text-due-today" },
  ok: { label: "In stock", className: "bg-[#e6f2eb] text-filed" },
  over: { label: "In stock", className: "bg-[#e6f2eb] text-filed" },
};

/** "In stock · 130", "Low · 4", "Out of stock". */
export function StockBadge({ level }: { level: StockLevel | null | undefined }) {
  if (!level) return <span className="text-meta text-ink-3">Not in Inventory</span>;
  if (!level.state) return <span className="text-meta text-ink-3">Not counted</span>;
  const s = STATE[level.state];
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-meta font-medium whitespace-nowrap ${s.className}`}>
      {s.label}
      {level.state !== "out" && <span className="tabular-nums">· {level.available.toLocaleString()}</span>}
    </span>
  );
}

/** Per warehouse: "Manila 30 · Cebu 100", and what's on its way. */
export function StockWhere({ level }: { level: StockLevel | null | undefined }) {
  if (!level || !level.state) return null;
  const parts = level.warehouses.filter((w) => w.available > 0 || w.inTransit > 0);
  if (parts.length === 0) return level.inTransit > 0 ? <p className="mt-0.5 text-meta text-ink-3">{level.inTransit.toLocaleString()} on the way</p> : null;
  return (
    <p className="mt-0.5 text-meta text-ink-3">
      {parts
        .map((w) => `${w.name} ${w.available.toLocaleString()}${w.inTransit > 0 ? ` (+${w.inTransit.toLocaleString()} coming)` : ""}`)
        .join(" · ")}
    </p>
  );
}

/** Bring the product list over from Inventory now. */
export function SyncNow() {
  const [pending, start] = useTransition();
  return (
    <Button
      loading={pending}
      icon={<RefreshCw className="size-4" aria-hidden />}
      onClick={() =>
        start(async () => {
          const result = await syncProducts();
          if (!result.ok) {
            toast.error(result.error);
            return;
          }
          const { added, updated, switchedOff } = result.data;
          const said = [added && `${added} added`, updated && `${updated} changed`, switchedOff && `${switchedOff} deactivated`].filter(Boolean).join(", ");
          toast.success("Products are up to date with Inventory", { description: said || "Nothing had changed." });
        })
      }
    >
      Sync now
    </Button>
  );
}
