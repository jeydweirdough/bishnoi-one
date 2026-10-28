import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { OrganisationChart } from "./chart";
import { loadOrganisation } from "./load";

/** The company's org chart in the Admin Console (feature plan step 4): for its administrators. */
export async function Organisation() {
  const data = await loadOrganisation();
  return (
    <>
      <PageHeader title="Organisation">
        {data ? <>Your divisions, departments and teams, their heads, your branches, and where each person sits. Every app reads it from here.</> : null}
      </PageHeader>
      {data ? (
        <OrganisationChart data={data} />
      ) : (
        <Sheet>
          <Empty icon="teams" title="No access to the org chart">
            Only your company&apos;s administrators keep the org chart. Ask one of them if something needs to change.
          </Empty>
        </Sheet>
      )}
    </>
  );
}
