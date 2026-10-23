import { load } from "@/src/platform/lib/api";
import type { Prompt } from "@/src/modules/crm/actions/attention";
import { AttentionCard } from "@/src/modules/crm/components/attention";
import { withCrmPages } from "@/src/modules/crm/lib/page";

/** The home page's "Needs your attention", loaded on its own so the rest of the page never waits for it. */
export async function AttentionPanel({ skip = [] }: { skip?: string[] }) {
  const prompts = await load<Prompt[]>("/attention").then(withCrmPages).catch(() => [] as Prompt[]);
  // `skip`: kinds the page already shows (the month's target, on a salesperson's Home).
  return <AttentionCard prompts={prompts.filter((p) => !skip.includes(p.kind))} />;
}
