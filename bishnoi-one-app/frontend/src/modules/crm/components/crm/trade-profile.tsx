import { Pill } from "@/src/platform/ui/figures";
import { CREDIT_TONES } from "@/src/modules/crm/components/crm/credit-tones";
import { Later } from "@/src/platform/ui/later";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { Bone } from "@/src/platform/ui/skeleton";
import type { Format } from "@/src/platform/lib/format";
import type { TradeProfile } from "@/src/platform/lib/types";

// A B2B customer's trade profile, worked out from their orders and Finance's
// invoices (app/trade.py), never typed: where they stand on credit, how much
// they bring in a year and how they rank for it, and the products they carry.

const FROM_WORDS = { order: "orders", deal: "deals won", invoice: "invoices" } as const;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-rule py-3 first:border-t-0 first:pt-1">
      <p className="text-meta font-medium text-ink-2">{label}</p>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function Loaded({ trade, fmt }: { trade: TradeProfile; fmt: Format }) {
  if (!trade.applies) return null;
  const { credit, profile, carried } = trade;
  return (
    <>
      <Row label="Profile">
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone={profile.level === "high" ? "ink" : profile.level ? "good" : "plain"} dot={false}>
            {profile.label}
          </Pill>
          {profile.rank && (
            <span className="text-meta text-ink-3">
              {profile.rank} of {profile.of} B2B customers
            </span>
          )}
        </div>
        <p className="mt-1.5 text-sm text-ink">
          <span className="font-semibold tabular-nums">{fmt.peso(profile.totalCentavos)}</span> over the last 12 months
        </p>
        <p className="text-meta text-ink-3">
          GetMeds {fmt.peso(profile.getmedsCentavos)} · 2MG {fmt.peso(profile.twoMgCentavos)}
          {profile.source === "deals" ? " · GetMeds from deals won (Finance can't be asked)" : ""}
        </p>
      </Row>
      <Row label="Credit status">
        <Pill tone={credit.status ? CREDIT_TONES[credit.status] : "plain"}>{credit.label}</Pill>
        <p className="mt-1.5 text-meta text-ink-2">{credit.detail}</p>
        {credit.owedCentavos > 0 && (
          <p className="text-meta text-ink-3">
            {fmt.peso(credit.owedCentavos)} owed on {credit.openInvoices} {credit.openInvoices === 1 ? "invoice" : "invoices"}
            {credit.overdueCentavos > 0 ? ` · ${fmt.peso(credit.overdueCentavos)} past due` : ""}
          </p>
        )}
      </Row>
      <Row label="Products they carry">
        {carried.length === 0 ? (
          <p className="text-meta text-ink-3">Fills in from their orders, deals won and Finance&apos;s invoices.</p>
        ) : (
          <ul className="space-y-1.5">
            {carried.slice(0, 8).map((p) => (
              <li key={p.id ?? p.name} className="flex items-baseline justify-between gap-3 text-sm">
                <span className="min-w-0 truncate text-ink">{p.name}</span>
                <span className="shrink-0 text-meta text-ink-3 tabular-nums" title={`From ${p.from.map((f) => FROM_WORDS[f]).join(", ")}`}>
                  {p.times}× {p.lastOn ? `· ${fmt.dateLabel(p.lastOn)}` : ""}
                </span>
              </li>
            ))}
            {carried.length > 8 && <li className="text-meta text-ink-3">And {carried.length - 8} more.</li>}
          </ul>
        )}
      </Row>
    </>
  );
}

/** The card, drawn at once with its title; the figures fill in when Finance answers. */
export function TradeProfileCard({ trade, fmt }: { trade: Promise<TradeProfile>; fmt: Format }) {
  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle icon="money">Trade profile</SectionTitle>
      <div className="mt-2">
        <Later
          data={trade}
          fallback={
            <div className="space-y-4 py-1" role="status" aria-label="Loading">
              {["Profile", "Credit status", "Products they carry"].map((label) => (
                <div key={label}>
                  <p className="text-meta font-medium text-ink-2">{label}</p>
                  <Bone className="mt-2 h-5 w-28" />
                  <Bone className="mt-2 h-3 w-44" />
                </div>
              ))}
            </div>
          }
        >
          {(t) => <Loaded trade={t} fmt={fmt} />}
        </Later>
      </div>
      <p className="mt-1 border-t border-rule pt-2.5 text-[0.6875rem] text-ink-3">Worked out from their orders and Finance&apos;s invoices; nothing here is typed.</p>
    </Sheet>
  );
}
