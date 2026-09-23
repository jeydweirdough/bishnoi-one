import { Bars } from "@/src/platform/ui/bars";
import { Figure } from "@/src/platform/ui/figure";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { moduleBase } from "@/src/platform/lib/apps";
import { departmentModule } from "@/src/platform/lib/module";
import type { FinanceSummary } from "@/src/platform/lib/types";

// Finance's own overview: what is waiting to be decided, across every division
// this person looks after.

export const metadata = { title: "Finance" };

type Props = {
  params: Promise<{ module: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function Page({ params }: Props) {
  const { module } = await params;
  const mod = await departmentModule(module, "finance");
  const { counts } = await load<FinanceSummary>("/finance/summary");
  // Its own pages: "/approvals" in this app, "/m/finance/approvals" in the
  // shell. The screen says which page, not which address.
  const base = moduleBase(module);
  return (
    <>
      <PageHeader title={mod.name}>Quotes waiting on Finance, from every division you look after.</PageHeader>
      <Sheet className="mb-5 grid divide-y divide-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <Figure label="Approvals waiting" value={counts.approvals} flag href={`${base}/approvals`} />
        <Figure label="Guarantee letters to check" value={counts.letters} flag href={`${base}/letters`} />
        <Figure label="Letter payments to record" value={counts.payments} href={`${base}/payments`} />
      </Sheet>
      <Sheet className="mb-5 px-5 pt-4 pb-4">
        <SectionTitle icon="approvals">What&apos;s waiting</SectionTitle>
        {/* The same measure three times — things waiting on Finance — so one
            hue and the row names itself. Length is the comparison. */}
        <Bars
          rows={[
            { label: "Approvals", value: counts.approvals, href: `${base}/approvals`, flag: true },
            { label: "Guarantee letters", value: counts.letters, href: `${base}/letters`, flag: true },
            { label: "Letter payments", value: counts.payments, href: `${base}/payments` },
          ]}
          unit="waiting"
        />
      </Sheet>

      <Sheet className="px-5 py-4">
        <SectionTitle icon="inbox">What lands here</SectionTitle>
        <dl className="mt-2 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="font-semibold">Approvals</dt>
            <dd className="text-ink-2">Quotes at a price that needs approval, such as a Special Price, and discounts over a division&apos;s limit.</dd>
          </div>
          <div>
            <dt className="font-semibold">Guarantee letters</dt>
            <dd className="text-ink-2">DSWD, PCSO and other letters to check against the uploaded file before anything is released.</dd>
          </div>
          <div>
            <dt className="font-semibold">Letter payments</dt>
            <dd className="text-ink-2">What the issuer has paid on a verified letter, until it&apos;s paid in full.</dd>
          </div>
        </dl>
      </Sheet>
    </>
  );
}
