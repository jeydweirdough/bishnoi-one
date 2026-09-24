import Link from "next/link";
import type { Format } from "@/src/platform/lib/format";
import { DeleteVisit } from "./delete-visit";
import type { Visit } from "./types";
import { outcomeOf } from "./words";

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
                    <Link href={`/companies/${v.company.id}`} className="text-hema hover:underline">
                      {v.company.name}
                    </Link>
                  </>
                )}
              </p>
              <p className="text-meta text-ink-3">
                {fmt.whenLabel(v.visitedAt, today)}
                {showWho && <> · {v.owner.name}</>}
                {v.receiptNo && <> · Receipt {v.receiptNo}</>}
              </p>
              {v.notes && <p className="mt-1 text-sm text-ink-2">{v.notes}</p>}
            </div>
            {v.outcome === "collected" && <span className="shrink-0 pt-0.5 text-sm font-semibold tabular-nums">{fmt.peso(v.amountCentavos)}</span>}
            {v.can.delete && <DeleteVisit id={v.id} doctor={v.company.name} />}
          </li>
        );
      })}
    </ul>
  );
}
