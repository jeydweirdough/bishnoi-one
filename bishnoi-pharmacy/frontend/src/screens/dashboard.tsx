import { ClipboardPlus, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Figure } from "@/src/platform/ui/figure";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/bits";
import { pageFor } from "../lib/page";
import type { Dashboard } from "../lib/types";

export const metadata = { title: "Dashboard" };

/**
 * What needs doing now, in the order the work moves: prescriptions waiting to
 * be checked, then verified ones waiting to be dispensed, then the stock that
 * will stop either. Each number opens the list behind it.
 */
export default async function DashboardPage() {
  const { me, fmt, allowed, may } = await pageFor("dashboard.view");
  if (!allowed) return <NoAccess what="the dashboard" />;
  const d = await load<Dashboard>("/dashboard");

  return (
    <>
      <PageHeader
        title={`${fmt.greeting()}, ${me.user.fullName.split(" ")[0]}`}
        actions={
          <>
            {may("sales.create") && (
              <LinkButton href="/sales/new" icon={<ShoppingCart className="size-4" aria-hidden />}>
                Counter sale
              </LinkButton>
            )}
            {may("prescriptions.create") && (
              <LinkButton href="/prescriptions/new" variant="primary" icon={<ClipboardPlus className="size-4" aria-hidden />}>
                Receive prescription
              </LinkButton>
            )}
          </>
        }
      >
        {fmt.dateLabel(d.today)} · {d.sales.count} sale{d.sales.count === 1 ? "" : "s"} today, {fmt.peso(d.sales.totalCentavos)} ·{" "}
        {d.dispensing.today} dispensing{d.dispensing.today === 1 ? "" : "s"} ({d.dispensing.unitsToday} units)
      </PageHeader>

      <div className="grid gap-4 lg:grid-cols-2">
        <Sheet className="px-5 pt-5 pb-2">
          <SectionTitle icon="prescriptions">Prescriptions to check</SectionTitle>
          <p className="mt-1 text-meta text-ink-3">Checked and verified before anything is dispensed.</p>
          <div className="-mx-5 mt-2 grid grid-cols-3 divide-x divide-rule">
            <Figure label="In the inbox" value={d.prescriptions.inbox} href="/prescriptions?view=inbox" />
            <Figure label="Being checked" value={d.prescriptions.pending} href="/prescriptions?view=pending" />
            <Figure label="Need clarification" value={d.prescriptions.needsClarification} href="/prescriptions?view=attention" flag />
          </div>
        </Sheet>

        <Sheet className="px-5 pt-5 pb-2">
          <SectionTitle icon="dispensing">Verified, to dispense</SectionTitle>
          <p className="mt-1 text-meta text-ink-3">The pharmacist picks the batch each medicine comes from.</p>
          <div className="-mx-5 mt-2 grid grid-cols-3 divide-x divide-rule">
            <Figure label="In the queue" value={d.dispensing.queue} href="/dispensing" />
            <Figure label="Partly dispensed" value={d.dispensing.partial} href="/dispensing?view=partial" />
            <Figure label="Dispensed today" value={d.dispensing.today} href="/dispensing?view=history" />
          </div>
        </Sheet>

        <Sheet className="px-5 pt-5 pb-2 lg:col-span-2">
          <SectionTitle icon="batches">Stock that needs a look</SectionTitle>
          <div className="-mx-5 mt-2 grid grid-cols-2 divide-rule sm:grid-cols-4 sm:divide-x">
            <Figure label="Low on stock" value={d.stock.low} href="/stock?view=low" flag />
            <Figure label={`Expiring within ${d.expiryWarningDays} days`} value={d.stock.expiring} href="/batches?view=expiring" flag />
            <Figure label="Expired, still on the shelf" value={d.stock.expired} href="/batches?view=expired" flag />
            <Figure label="In quarantine" value={d.stock.quarantined} href="/batches?view=held" />
          </div>
          {d.stock.lowItems.length > 0 && (
            <ul className="-mx-5 mt-2 divide-y divide-rule border-t border-rule">
              {d.stock.lowItems.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-4 px-5 py-2.5 text-sm">
                  <Link href={`/medicines/${m.id}`} className="min-w-0 truncate font-semibold text-hema hover:underline">
                    {m.label}
                  </Link>
                  <span className="shrink-0 text-meta text-ink-2 tabular-nums">
                    {m.available} {m.unit}(s) left · reorder at {m.reorderLevel}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Sheet>
      </div>
    </>
  );
}
