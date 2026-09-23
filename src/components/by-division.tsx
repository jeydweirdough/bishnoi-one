import Link from "next/link";
import { Sparkline } from "@/src/platform/ui/sparkline";
import { TrendChart } from "../components/trend-chart";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { rateLabel } from "@/src/platform/lib/labels";
import type { Org, RetentionByDivision } from "@/src/platform/lib/types";

/** Retention division by division, for whoever reports in more than one. One
 *  view of the Retention page rather than a page of its own: it answers the
 *  same question, only grouped differently. */
export function ByDivision({ data, org }: { data: RetentionByDivision; org: Org }) {
  return (
    <>
      <Sheet className="mb-5">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <thead>
              <tr className="border-b border-rule text-caps text-ink-3 uppercase">
                <th scope="col" className="px-5 py-3 font-semibold">Division</th>
                <th scope="col" className="px-3 py-3 text-right font-semibold">Retention</th>
                <th scope="col" className="px-3 py-3 text-right font-semibold">Kept</th>
                <th scope="col" className="px-3 py-3 text-right font-semibold">New</th>
                <th scope="col" className="px-3 py-3 text-right font-semibold">At risk now</th>
                <th scope="col" className="px-3 py-3 text-right font-semibold">Customers</th>
                <th scope="col" className="px-5 py-3 font-semibold">Last 12 months</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule tabular-nums">
              {data.divisions.map((d) => (
                <tr key={d.code} className="hover:bg-bench/40">
                  <th scope="row" className="px-5 py-3 text-left font-normal">
                    <Link href={`/retention?view=team&division=${d.code}`} className="font-semibold text-hema hover:underline">
                      {d.name}
                    </Link>
                    <span className="block text-meta text-ink-3">
                      Window {d.rules.lostDays} days · at risk after {d.rules.atRiskDays}
                    </span>
                  </th>
                  <td className="px-3 py-3 text-right text-base font-semibold">{rateLabel(d.summary.rate)}</td>
                  <td className="px-3 py-3 text-right text-ink-2">{d.summary.base ? `${d.summary.retained} of ${d.summary.base}` : "—"}</td>
                  <td className="px-3 py-3 text-right">{d.summary.new}</td>
                  <td className="px-3 py-3 text-right">{d.summary.atRisk}</td>
                  <td className="px-3 py-3 text-right">{d.summary.customers}</td>
                  <td className="px-5 py-3">
                    <Sparkline points={d.trend} />
                  </td>
                </tr>
              ))}
            </tbody>
            {data.divisions.length > 1 && (
              <tfoot className="border-t border-ink tabular-nums">
                <tr>
                  <th scope="row" className="px-5 py-3 text-left font-semibold">All of them</th>
                  <td className="px-3 py-3 text-right text-base font-semibold">{rateLabel(data.total.summary.rate)}</td>
                  <td className="px-3 py-3 text-right text-ink-2">
                    {data.total.summary.base ? `${data.total.summary.retained} of ${data.total.summary.base}` : "—"}
                  </td>
                  <td className="px-3 py-3 text-right">{data.total.summary.new}</td>
                  <td className="px-3 py-3 text-right">{data.total.summary.atRisk}</td>
                  <td className="px-3 py-3 text-right">{data.total.summary.customers}</td>
                  <td className="px-5 py-3">
                    <Sparkline points={data.total.trend} />
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-4">
        <SectionTitle icon="trend">{data.divisions.length > 1 ? "All divisions together, by month" : `${data.divisions[0].name}, by month`}</SectionTitle>
        <TrendChart points={data.total.trend} title="Retention by month, all your divisions together" org={org} />
      </Sheet>
    </>
  );
}
