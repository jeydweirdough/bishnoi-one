import type { Format } from "@/src/platform/lib/format";
import type { QuoteTax } from "@/src/platform/lib/types";
import { SOURCE_WORDS } from "@/src/modules/crm/components/catalogue/price-rules-types";

/** Finance's tax on a quote, as the invoice will show it: its summary rows and the amount due. */
export function TaxSummary({ tax, fmt }: { tax: QuoteTax; fmt: Format }) {
  return (
    <div className="mt-2 space-y-1 border-t border-rule pt-2 text-meta text-ink-2">
      <p className="text-caps text-ink-3 uppercase">
        {tax.document} · {tax.regimeName}
      </p>
      {tax.summary
        .filter((row) => row.amountCentavos > 0)
        .map((row) => (
          <p key={row.key} className="flex justify-between">
            <span>{row.label}</span>
            <span className="tabular-nums">{fmt.peso(row.amountCentavos)}</span>
          </p>
        ))}
      <p className="flex justify-between text-sm font-semibold text-ink">
        <span>Amount due{tax.pricesIncludeTax ? " (VAT included)" : ""}</span>
        <span className="tabular-nums">{fmt.peso(tax.totalDueCentavos)}</span>
      </p>
      {tax.notice && <p className="text-center font-semibold">{tax.notice}</p>}
    </div>
  );
}

/** Where a line's price came from, when it isn't the list price. */
export function PriceSource({ source }: { source?: string | null }) {
  if (!source || source === "list_price") return null;
  return <span className="block text-meta text-ink-3">{SOURCE_WORDS[source] ?? source}</span>;
}

/** A line's volume discount and surcharge, from the price rules. */
export function RuleAdjustments({ line, fmt }: { line: { volumeName?: string | null; volumeDiscountCentavos?: number; surchargeName?: string | null; surchargeCentavos?: number }; fmt: Format }) {
  return (
    <>
      {!!line.volumeDiscountCentavos && (
        <span className="block">
          {line.volumeName ?? "Volume"} (−{fmt.peso(line.volumeDiscountCentavos)})
        </span>
      )}
      {!!line.surchargeCentavos && (
        <span className="block">
          {line.surchargeName ?? "Surcharge"} (+{fmt.peso(line.surchargeCentavos)})
        </span>
      )}
    </>
  );
}
