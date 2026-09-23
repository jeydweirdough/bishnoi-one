import { TeamPricesEditor } from "../components/team-prices";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { salesWorkspace, teamsFor } from "@/src/platform/lib/module";
import type { TeamPrices } from "@/src/platform/lib/types";

export const metadata = { title: "Prices" };

export default async function PricesPage() {
  const [ws, me] = await Promise.all([salesWorkspace(), getCompanyMe()]);
  // Every team whose prices this person may set, in any division they sell in:
  // their own as a team lead, all of a division's as its head. The API checks
  // again on every call.
  const teams = teamsFor(ws, "prices");

  if (teams.length === 0) {
    return (
      <Sheet className="px-6 py-10 text-center">
        <h1 className="text-heading">Prices are set by team leads</h1>
        <p className="mx-auto mt-1 max-w-md text-ink-2">
          You quote from your division&apos;s prices, but what a team charges is its lead&apos;s to set. If that should be you,
          ask one of your admins.
        </p>
        <LinkButton href="/overview" className="mt-5">
          Go to your overview
        </LinkButton>
      </Sheet>
    );
  }

  const first = teams[0];
  const sheet = await load<TeamPrices>(`/sales/prices?division=${enc(first.division)}&team=${enc(first.code)}`);
  return (
    <>
      <PageHeader title="Prices">
        What your team charges, over the company price list. A price you don&apos;t set follows the company&apos;s, so nothing
        changes until you say so.
      </PageHeader>
      <TeamPricesEditor teams={teams} initial={sheet} org={me.org} />
    </>
  );
}
