import Link from "next/link";
import type { ReactNode } from "react";
import { Icon, type IconName } from "@/src/platform/ui/icons";

// A record's page, laid out one way everywhere: a tinted panel holding the
// record's picture side (pictures, barcode) and its facts side (three figures,
// then its information in labelled pairs, then what it's spread across).
// Server components; nothing here holds state.

/** The panel: the record's left column beside its facts. Without `side`, the facts take the width. */
export function DetailPanel({ side, children }: { side?: ReactNode; children: ReactNode }) {
  return (
    <div className={`mt-5 grid gap-4 rounded-[26px] border border-rule bg-[#f4f4f1] p-3 sm:p-4 ${side ? "lg:grid-cols-[19rem_minmax(0,1fr)]" : ""}`}>
      {side && <div className="min-w-0 space-y-4">{side}</div>}
      <div className="min-w-0 space-y-4">{children}</div>
    </div>
  );
}

/** A white card inside the panel. */
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-[20px] border border-rule bg-sheet ${className}`}>{children}</div>;
}

/** The record's headline numbers: a label, then the number under it. */
export function StatCards({ items }: { items: { label: string; value: ReactNode; flag?: boolean; href?: string; note?: ReactNode }[] }) {
  return (
    <dl className={`grid gap-3 ${items.length >= 4 ? "grid-cols-2 xl:grid-cols-4" : "grid-cols-1 sm:grid-cols-3"}`}>
      {items.map((s) => (
        <div key={s.label} className={`rounded-[20px] border bg-sheet px-5 py-4 ${s.flag ? "border-danger/40" : "border-rule"}`}>
          <dt className={`text-sm ${s.flag ? "text-danger" : "text-ink-2"}`}>{s.label}</dt>
          <dd className="mt-1 text-[1.5rem] leading-tight font-semibold tracking-[-0.02em] text-ink tabular-nums">
            {s.href ? (
              <Link href={s.href} className="hover:underline">
                {s.value}
              </Link>
            ) : (
              s.value
            )}
          </dd>
          {s.note && <dd className="mt-0.5 text-meta text-ink-3">{s.note}</dd>}
        </div>
      ))}
    </dl>
  );
}

/** One part of the record's information: a heading with its icon, then label and value in pairs, two to a row. */
export function InfoSection({ icon, title, action, items, children }: { icon: IconName; title: string; action?: ReactNode; items: [string, ReactNode][]; children?: ReactNode }) {
  return (
    <section className="px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[1.0625rem] font-semibold text-ink">
          <Icon name={icon} className="size-[1.125rem] text-ink-2" />
          {title}
        </h2>
        {action}
      </div>
      <dl className="mt-3 grid gap-x-8 gap-y-3 sm:grid-cols-2">
        {items.map(([label, value]) => (
          <div key={label} className="grid grid-cols-[8.5rem_minmax(0,1fr)] items-baseline gap-3 text-sm">
            <dt className="font-semibold text-ink">{label}</dt>
            <dd className="min-w-0 break-words text-ink-2">{value ?? <span className="text-ink-3">—</span>}</dd>
          </div>
        ))}
      </dl>
      {children}
    </section>
  );
}

/** Information sections in one card, ruled between. */
export function InfoCard({ children }: { children: ReactNode }) {
  return <Card className="divide-y divide-rule">{children}</Card>;
}

/** A small pill beside a value: "Margin 53%". */
export function Pill({ children }: { children: ReactNode }) {
  return <span className="ml-2 inline-flex h-5 items-center rounded-full border border-rule-strong px-2 text-[0.6875rem] font-medium text-ink-2">{children}</span>;
}

/**
 * What the record is spread across (its warehouses, its products), one row
 * each: an icon, the name and a line under it, a status pill, and a bar for its
 * share.
 */
export function BarList({ title, icon, action, rows, empty }: {
  title: string;
  icon: IconName;
  action?: ReactNode;
  rows: { key: string; href?: string; name: ReactNode; sub?: ReactNode; pill?: ReactNode; share: number }[];
  empty?: string;
}) {
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-2 px-5 pt-4 pb-2">
        <h2 className="flex items-center gap-2 text-[1.0625rem] font-semibold text-ink">
          <Icon name={icon} className="size-[1.125rem] text-ink-2" />
          {title}
        </h2>
        {action}
      </div>
      {rows.length === 0 ? (
        <p className="px-5 pb-4 text-meta text-ink-3">{empty ?? "Nothing yet."}</p>
      ) : (
        <ul className="divide-y divide-rule">
          {rows.map((r) => (
            <li key={r.key} className="relative grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 px-5 py-3.5 sm:grid-cols-[2rem_minmax(0,1fr)_auto_9rem]">
              <Icon name={icon} className="size-[1.125rem] text-ink-3" />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">
                  {r.href ? (
                    <Link href={r.href} className="after:absolute after:inset-0 hover:underline">
                      {r.name}
                    </Link>
                  ) : (
                    r.name
                  )}
                </p>
                {r.sub && <p className="truncate text-meta text-ink-3">{r.sub}</p>}
              </div>
              <div className="justify-self-end">{r.pill}</div>
              <div className="col-span-3 h-1.5 overflow-hidden rounded-full bg-rule sm:col-span-1" aria-hidden>
                <div className="h-full rounded-full bg-ink" style={{ width: `${Math.max(0, Math.min(1, r.share)) * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// Code 128 bar widths (bar, space, bar...), by symbol value; 103-105 start A/B/C, 106 stop.
const CODE128 = [
  "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
  "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
  "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
  "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
  "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
  "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
  "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
  "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
  "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
  "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
  "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
];

/** The symbols for a value: all digits, even count, in pairs (Code C); otherwise one by one (Code B). */
function code128(value: string): number[] | null {
  if (/^(\d\d)+$/.test(value)) {
    const data = value.match(/\d\d/g)!.map(Number);
    return [105, ...data];
  }
  if (![...value].every((c) => c.charCodeAt(0) >= 32 && c.charCodeAt(0) <= 126)) return null;
  return [104, ...[...value].map((c) => c.charCodeAt(0) - 32)];
}

/** A product's barcode, drawn so it can be scanned off the screen, with its digits under it. */
export function Barcode({ value }: { value: string }) {
  const symbols = code128(value);
  if (!symbols) return <p className="font-mono text-lg tracking-[0.2em] text-ink">{value}</p>;
  const check = symbols.reduce((sum, v, i) => sum + v * (i === 0 ? 1 : i), 0) % 103;
  const widths = [...symbols, check, 106].map((v) => CODE128[v]).join("");
  const bars: { x: number; w: number }[] = [];
  let x = 10; // the quiet zone
  [...widths].forEach((d, i) => {
    const w = Number(d);
    if (i % 2 === 0) bars.push({ x, w });
    x += w;
  });
  const total = x + 10;
  return (
    <figure className="flex flex-col items-center">
      <svg viewBox={`0 0 ${total} 60`} className="h-24 w-full max-w-64" preserveAspectRatio="none" role="img" aria-label={`Barcode ${value}`}>
        {bars.map((b) => (
          <rect key={b.x} x={b.x} y={0} width={b.w} height={60} fill="#141414" />
        ))}
      </svg>
      <figcaption className="mt-1.5 font-mono text-base tracking-[0.25em] text-ink">{value}</figcaption>
    </figure>
  );
}
