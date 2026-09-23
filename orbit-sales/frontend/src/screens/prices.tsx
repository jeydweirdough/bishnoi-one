import { TeamPricesEditor, type PricedTeam } from "../components/team-prices";
import { CatalogueTabs } from "../components/catalogue/catalogue-tabs";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { TeamPrices } from "@/src/platform/lib/types";

export const metadata = { title: "Special prices" };

export default async function PricesPage() {
  const me = await getCompanyMe();
  // Every team whose prices this person may set: their own, or any team with a
  // role that reaches every record. The API checks again on every call.
  const teams = can(me, "products.prices") ? await load<PricedTeam[]>("/prices/teams") : [];

  if (teams.length === 0) {
    return (
      <Sheet className="px-6 py-10 text-center">
        <h1 className="text-heading">Special prices are set by team leads</h1>
        <p className="mx-auto mt-1 max-w-md text-ink-2">
          You quote from the standard price list and your team&apos;s own prices, but what a team charges is its lead&apos;s to
          set{can(me, "products.prices") && !me.team ? ", and you aren't in a team" : ""}. If that should be you, ask an administrator.
        </p>
        <LinkButton href="/" className="mt-5">
          Go to your overview
        </LinkButton>
      </Sheet>
    );
  }

  const sheet = await load<TeamPrices>(`/prices?team=${enc(teams.find((t) => t.id === me.team?.id)?.id ?? teams[0].id)}`);
  return (
    <>
      <PageHeader title="Products & services">
        Your team&apos;s special prices: what the team charges for each product, over the standard price list. A price you don&apos;t set follows the standard one, so nothing
        changes until you say so.
      </PageHeader>
      <CatalogueTabs me={me} current="/prices" />
      <TeamPricesEditor teams={teams} initial={sheet} org={me.org} />
    </>
  );
}
