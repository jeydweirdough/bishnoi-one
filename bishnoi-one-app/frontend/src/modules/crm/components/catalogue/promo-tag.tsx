import { Check, Package, Tag } from "lucide-react";
import type { ReactNode } from "react";
import { promoTerms } from "@/src/platform/lib/labels";
import type { Format } from "@/src/platform/lib/format";
import type { PriceList, PromoTerms } from "@/src/platform/lib/types";

type Offer = PriceList["bundles"][number];

// A product on promo, shown the same way wherever it is picked or read: a
// coupon in the sale-tag yellow, with what it gives and how long it has left.
// Picked on a line, the promo goes with that line onto the deal and the quote.
// A product sold in a bundle says so the same way: the set, its price, and
// (on a quote) a tap to quote the set instead.

/** The promos a product can be sold under, from the customer's price list. */
export function promosFor(promos: PromoTerms[], productId: string): PromoTerms[] {
  return productId ? promos.filter((p) => p.productIds === null || p.productIds.includes(productId)) : [];
}

/** The bundles a product is part of, from the customer's price list. */
export function bundlesWith(bundles: Offer[], productId: string): Offer[] {
  return productId ? bundles.filter((b) => b.items.some((i) => i.productId === productId)) : [];
}

/** The promo a newly picked product starts with: its only one, or none to choose between. */
export function startingPromo(promos: PromoTerms[], productId: string): string {
  const offered = promosFor(promos, productId);
  return offered.length === 1 ? offered[0].id : "";
}

/** "Ends today", "1 day left", "12 days left"; null without an end. Counted in whole days from today. */
export function timeLeft(endsOn: string | null): string | null {
  if (!endsOn) return null;
  const [y, m, d] = endsOn.split("-").map(Number);
  const now = new Date();
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((Date.UTC(y, m - 1, d) - today) / 86_400_000);
  if (days < 0) return "Ended";
  if (days === 0) return "Ends today";
  return `${days} ${days === 1 ? "day" : "days"} left`;
}

/** The small "Promo" mark beside a product's name in a picker. */
export function PromoFlag({ count = 1 }: { count?: number }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-promo px-1.5 py-px text-[0.6875rem] leading-4 font-semibold text-promo-ink">
      <Tag className="size-3" aria-hidden />
      {count > 1 ? `${count} promos` : "Promo"}
    </span>
  );
}

/** The small "Bundle" mark beside a product's name in a picker: it's also sold as part of a set. */
export function BundleFlag({ count = 1 }: { count?: number }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-promo-tint px-1.5 py-px text-[0.6875rem] leading-4 font-semibold text-promo-ink ring-1 ring-promo/60">
      <Package className="size-3" aria-hidden />
      {count > 1 ? `${count} bundles` : "Bundle"}
    </span>
  );
}

/** A picker option's label, with the promo and bundle marks when the product has them. */
export function withPromoFlag(label: ReactNode, count: number, bundles = 0) {
  return (
    <span className="flex min-w-0 items-center justify-between gap-2">
      <span className="min-w-0 truncate">{label}</span>
      {(count > 0 || bundles > 0) && (
        <span className="flex shrink-0 gap-1">
          {count > 0 && <PromoFlag count={count} />}
          {bundles > 0 && <BundleFlag count={bundles} />}
        </span>
      )}
    </span>
  );
}

/** One promo as a coupon. With onToggle it is a button: tapped on, it applies to the line; tapped again, it comes off. */
export function PromoTag({ promo, fmt, applied = false, onToggle }: { promo: PromoTerms; fmt: Format; applied?: boolean; onToggle?: () => void }) {
  const left = timeLeft(promo.endsOn);
  const body = (
    <>
      {/* The stub, as on a paper coupon. */}
      <span aria-hidden className={`grid w-8 shrink-0 place-items-center self-stretch ${applied ? "bg-promo" : "bg-promo/70"}`}>
        {applied ? <Check className="size-4 text-promo-ink" strokeWidth={2.5} /> : <Tag className="size-4 text-promo-ink" />}
      </span>
      <span className="min-w-0 border-l border-dashed border-promo-ink/30 px-3 py-1.5 text-left">
        <span className="block truncate text-sm leading-5 font-semibold text-ink">{promoTerms(fmt, promo)}</span>
        <span className="block truncate text-meta text-ink-2">
          {promo.name}
          {left && <span className="font-medium text-promo-ink"> · {left}</span>}
        </span>
        {onToggle && <span className="block text-[0.6875rem] leading-4 font-semibold text-promo-ink">{applied ? "Applied · tap to remove" : "Tap to apply"}</span>}
      </span>
    </>
  );
  const look = `inline-flex max-w-full min-w-0 items-stretch overflow-hidden rounded-md border ${
    applied ? "border-promo bg-promo-tint shadow-sm" : "border-promo/60 bg-sheet"
  }`;
  if (!onToggle) return <span className={look}>{body}</span>;
  return (
    <button suppressHydrationWarning type="button" aria-pressed={applied} onClick={onToggle} className={`${look} transition-colors hover:border-promo hover:bg-promo-tint focus-visible:ring-2 focus-visible:ring-promo focus-visible:outline-none`}>
      {body}
    </button>
  );
}

/** A line's promos, to apply one (or none). Nothing at all when the product has none. */
export function PromoTags({
  promos,
  fmt,
  appliedId,
  onPick,
  label,
}: {
  promos: PromoTerms[];
  fmt: Format;
  appliedId: string;
  onPick: (id: string) => void;
  /** Who they're for, for screen readers: "Line 2". */
  label: string;
}) {
  if (promos.length === 0) return null;
  return (
    <div role="group" aria-label={`${label}: promos`} className="flex flex-wrap gap-2">
      {promos.map((p) => (
        <PromoTag key={p.id} promo={p} fmt={fmt} applied={p.id === appliedId} onToggle={() => onPick(p.id === appliedId ? "" : p.id)} />
      ))}
    </div>
  );
}

/**
 * A bundle the picked product is part of, as a coupon: what's in the set and
 * its price. With onUse (a quote) it is a button that quotes the set on this
 * line instead; without (a deal, which holds products only) it is a reminder.
 */
export function BundleTag({ bundle, nameOf, fmt, onUse }: { bundle: Offer; nameOf: (productId: string) => string; fmt: Format; onUse?: () => void }) {
  const left = timeLeft(bundle.endsOn);
  const contents = bundle.items.map((i) => `${i.qty} × ${nameOf(i.productId)}`).join(" + ");
  const body = (
    <>
      <span aria-hidden className="grid w-8 shrink-0 place-items-center self-stretch bg-promo/70">
        <Package className="size-4 text-promo-ink" />
      </span>
      <span className="min-w-0 border-l border-dashed border-promo-ink/30 px-3 py-1.5 text-left">
        <span className="block truncate text-sm leading-5 font-semibold text-ink">
          {bundle.name} · {fmt.peso(bundle.priceCentavos)} the set
        </span>
        <span className="block truncate text-meta text-ink-2">
          {contents}
          {left && <span className="font-medium text-promo-ink"> · {left}</span>}
        </span>
        <span className="block text-[0.6875rem] leading-4 font-semibold text-promo-ink">{onUse ? "Tap to quote the set" : "Quote it as a set"}</span>
      </span>
    </>
  );
  const look = "inline-flex max-w-full min-w-0 items-stretch overflow-hidden rounded-md border border-promo/60 bg-sheet";
  if (!onUse) return <span className={look}>{body}</span>;
  return (
    <button suppressHydrationWarning type="button" onClick={onUse} className={`${look} transition-colors hover:border-promo hover:bg-promo-tint focus-visible:ring-2 focus-visible:ring-promo focus-visible:outline-none`}>
      {body}
    </button>
  );
}

/** A promo as it went onto a saved line: its name and what it took off. */
export function AppliedPromo({ name, discountCentavos = 0, freeQuantity = 0, fmt }: { name: string; discountCentavos?: number; freeQuantity?: number; fmt: Format }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-md bg-promo-tint px-2 py-0.5 text-meta font-medium text-promo-ink ring-1 ring-promo/60">
      <Tag className="size-3 shrink-0" aria-hidden />
      <span className="truncate">{name}</span>
      {discountCentavos > 0 && <span className="shrink-0 tabular-nums">−{fmt.peso(discountCentavos)}</span>}
      {freeQuantity > 0 && <span className="shrink-0">+{freeQuantity} free</span>}
    </span>
  );
}
