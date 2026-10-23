import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Icon } from "@/src/modules/inventory/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import type { IconName } from "@/src/modules/inventory/platform/ui/icons";
import { loadSetup, missingFor, type Need, type Setup } from "@/src/modules/inventory/lib/setup";

/**
 * In place of a New page whose form can't be finished yet: what it needs
 * first, in order, each with a button that makes it and comes back here.
 * Null when nothing is missing, so the page shows its form.
 */
export function NeedsFirst({
  setup,
  needs,
  then,
  title,
  doing,
  crumbs,
  may,
}: {
  setup: Setup;
  needs: Need[];
  then: string;
  title: string;
  /** What this page does, in a phrase: "receive stock". */
  doing: string;
  crumbs?: { href: string; label: string }[];
  may: (permission: string) => boolean;
}) {
  const missing = missingFor(setup, needs, then);
  if (missing.length === 0) return null;
  return (
    <>
      <PageHeader title={title} crumbs={crumbs} />
      <Sheet className="max-w-2xl px-6 py-6">
        <span className="grid size-11 place-items-center rounded-lg bg-hema-tint text-sage-deep">
          <Icon name={missing[0].step.icon} className="size-5" />
        </span>
        <h2 className="mt-4 text-lg font-semibold text-ink">
          Complete setup to {doing}
        </h2>
        <p className="mt-1 text-sm text-ink-2">Required first: {missing.map((m) => m.says).join(", and ")}. You return to this page afterwards.</p>
        <ol className="mt-5 space-y-2.5">
          {missing.map((m, i) => (
            <li key={m.need} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rule px-4 py-3">
              <span className="flex items-center gap-3">
                <span className={`grid size-7 place-items-center rounded-full text-meta font-semibold ${i === 0 ? "bg-ink text-white" : "border border-rule-strong text-ink-3"}`}>{i + 1}</span>
                <span>
                  <span className="block text-sm font-semibold text-ink">{m.step.title}</span>
                  <span className="block text-meta text-ink-3">{m.step.why}</span>
                </span>
              </span>
              {may(m.step.permission) ? (
                <LinkButton href={m.href} size="sm" variant={i === 0 ? "primary" : "default"}>
                  {m.action}
                </LinkButton>
              ) : (
                <span className="text-meta text-ink-3">Requires an administrator</span>
              )}
            </li>
          ))}
        </ol>
        <Link href="/inventory" className="mt-5 inline-flex items-center gap-1 text-meta text-ink-3 hover:text-ink">
          View all setup steps on Home
          <ChevronRight className="size-3.5" aria-hidden />
        </Link>
      </Sheet>
    </>
  );
}

/**
 * An empty list, saying what to do next. Filtered: clear a filter. Otherwise,
 * if what this list holds needs something that isn't there yet (stock needs a
 * product), that first, coming back here after; else this list's own first one.
 */
export async function FirstStep({
  icon,
  title,
  body,
  needs = [],
  href,
  action,
  permission,
  filtered,
  clear,
  may,
}: {
  icon: IconName;
  title: string;
  body: string;
  needs?: Need[];
  /** Where this list's own first record is made. */
  href: string;
  action: string;
  permission: string;
  filtered: boolean;
  /** The list without its filters. */
  clear: string;
  may: (permission: string) => boolean;
}) {
  if (filtered) {
    return (
      <Empty icon={icon} title="No matching records" actions={<LinkButton href={clear}>Clear filters</LinkButton>}>
        Change or clear the filters to see more results.
      </Empty>
    );
  }
  const missing = needs.length ? missingFor(await loadSetup(), needs, href) : [];
  const first = missing[0];
  if (first) {
    return (
      <Empty
        icon={first.step.icon}
        title={`First, ${first.step.title.charAt(0).toLowerCase()}${first.step.title.slice(1)}`}
        actions={may(first.step.permission) ? <LinkButton href={first.href} variant="primary">{first.action}</LinkButton> : undefined}
      >
        {title}: {body} Requires {missing.map((m) => m.says).join(", and ")}{may(first.step.permission) ? ". You return to this page afterwards." : ". An administrator must set this up."}
      </Empty>
    );
  }
  return (
    <Empty icon={icon} title={title} actions={may(permission) ? <LinkButton href={href} variant="primary">{action}</LinkButton> : undefined}>
      {body}
    </Empty>
  );
}
