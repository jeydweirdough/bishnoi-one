import { PlatformConsole } from "../components/platform-console";
import { developersOnly } from "../components/gate";
import { PageHeader } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import type { PlatformCompany } from "@/src/platform/lib/types";

export const metadata = { title: "Companies" };

export default async function Page() {
  const stop = await developersOnly();
  if (stop) return stop;
  const data = await load<{ companies: PlatformCompany[] }>("/platform/companies");
  return (
    <>
      <PageHeader title="Companies">
        Every company on Orbit. You are in none of them — that is what lets you reach them all. Add one when a company wants to
        use the system, and open one when there is something to put right.
      </PageHeader>
      <PlatformConsole companies={data.companies} />
    </>
  );
}
