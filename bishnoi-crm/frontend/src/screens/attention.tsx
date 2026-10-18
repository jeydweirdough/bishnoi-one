import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import type { Prompt } from "../actions/attention";
import { AttentionList } from "../components/attention";

export const metadata = { title: "Needs your attention" };

/** Everything that needs this person, in one list: "See all" from the home page's panel. */
export default async function AttentionPage() {
  const prompts = await load<Prompt[]>("/attention");
  return (
    <>
      <PageHeader title="Needs your attention" crumbs={[{ href: "/", label: "Home" }]}>
        Most pressing first, each with the one thing to do. Put one aside for a week, or for good, with the ⋯ beside it.
      </PageHeader>
      <Sheet>
        <AttentionList prompts={prompts} />
      </Sheet>
    </>
  );
}
