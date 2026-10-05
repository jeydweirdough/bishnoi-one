import Link from "next/link";
import type { Format } from "@/src/platform/lib/format";
import { DeleteVisit } from "./delete-visit";
import type { Visit } from "./types";
import { distanceText, mapLink } from "./where";
import { outcomeOf, reactionOf } from "./words";

/** Where the visit was logged, against the clinic's pin: said plainly, with a map to check. */
function Place({ v }: { v: Visit }) {
  if (!v.location) return <span className="text-ink-3">No location</span>;
  const words =
    v.atClinic === true ? "At the clinic" : v.atClinic === false && v.distanceM !== null ? `${distanceText(v.distanceM)} from the clinic` : "Place saved";
  return (
    <a href={mapLink(v.location)} target="_blank" rel="noopener noreferrer" className={`hover:underline ${v.atClinic === false ? "font-semibold text-danger" : "text-ink-2"}`}>
      {words}
    </a>
  );
}

/** Visits, newest first: who went, what came of it, and any payment collected. */
export function VisitList({ visits, fmt, today, showDoctor = true, showWho = true }: { visits: Visit[]; fmt: Format; today: string; showDoctor?: boolean; showWho?: boolean }) {
  return (
    <ul className="divide-y divide-rule">
      {visits.map((v) => {
        const outcome = outcomeOf(v.outcome);
        return (
          <li key={v.id} className="flex items-start gap-3 py-3">
            <div className="min-w-0 flex-1">
              <p className="text-sm">
                <span className="font-semibold">{outcome.past}</span>
                {showDoctor && (
                  <>
                    {" · "}
                    <Link href={`/companies/${v.company.id}`} className="text-ink hover:underline">
                      {v.company.name}
                    </Link>
                  </>
                )}
              </p>
              <p className="text-meta text-ink-3">
                {fmt.whenLabel(v.visitedAt, today)}
                {showWho && <> · {v.owner.name}</>}
                {v.receiptNo && <> · Receipt {v.receiptNo}</>}
                {" · "}
                <Place v={v} />
              </p>
              {v.detailing.length > 0 && (
                <ol className="mt-1.5 space-y-0.5 text-sm">
                  {v.detailing.map((d) => {
                    const r = reactionOf(d.reaction);
                    return (
                      <li key={d.productId}>
                        <span className="font-medium">{d.productName}</span>
                        {": "}
                        <span className={r.tone === "good" ? "text-filed" : r.tone === "bad" ? "text-danger" : "text-ink-2"}>{r.label.toLowerCase()}</span>
                        {d.message && <span className="text-ink-3"> · {d.message}</span>}
                      </li>
                    );
                  })}
                </ol>
              )}
              {v.notes && <p className="mt-1 text-sm text-ink-2">{v.notes}</p>}
              {v.nextObjective && (
                <p className="mt-1 text-meta text-ink-3">
                  <span className="font-semibold text-ink-2">Next time:</span> {v.nextObjective}
                </p>
              )}
            </div>
            {v.outcome === "collected" && <span className="shrink-0 pt-0.5 text-sm font-semibold tabular-nums">{fmt.peso(v.amountCentavos)}</span>}
            {v.can.delete && <DeleteVisit id={v.id} doctor={v.company.name} />}
          </li>
        );
      })}
    </ul>
  );
}
