import { Check, ChevronRight, Lock } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import type { IconName } from "@/src/platform/ui/icons";
import { STEPS, blockedBy, loadSetup, missingFor, type Need, type Setup } from "../lib/setup";

/**
 * Home's "Get started": the setup steps in their order, each ticked once done.
 * The next one is open with its button; one that waits on another says which.
 * Gone once everything that must be done is.
 */
export function SetupGuide({ setup, may }: { setup: Setup; may: (permission: string) => boolean }) {
  const steps = STEPS.filter((s) => may(s.permission) || s.done(setup));
  const needed = steps.filter((s) => !s.optional);
  if (needed.every((s) => s.done(setup))) return null;
  const done = steps.filter((s) => s.done(setup)).length;
  const next = steps.find((s) => !s.done(setup) && !blockedBy(s, setup) && may(s.permission));
  const pct = Math.round((100 * done) / Math.max(1, steps.length));
  return (
    <Sheet className="mb-5 px-5 py-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Get started</h2>
          <p className="text-meta text-ink-3">Set Inventory up in this order: each step needs the one before it.</p>
        </div>
        <span className="flex items-center gap-3 text-meta text-ink-2">
          <span className="h-2 w-32 overflow-hidden rounded-full bg-mint-2">
            <span className="block h-full rounded-full bg-sage" style={{ width: `${pct}%` }} />
          </span>
          {done} of {steps.length} done
        </span>
      </div>
      <ol className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {steps.map((s, i) => {
          const isDone = s.done(setup);
          const waits = !isDone ? blockedBy(s, setup) : undefined;
          const isNext = s === next;
          return (
            <li
              key={s.key}
              className={`flex flex-col rounded-lg border px-4 py-3.5 ${isNext ? "border-ink bg-sheet shadow-[0_0_0_1px_var(--color-ink)]" : isDone ? "border-rule bg-hema-tint" : "border-rule bg-sheet"}`}
            >
              <span className="flex items-center gap-2.5">
                <span
                  className={`grid size-7 shrink-0 place-items-center rounded-full text-meta font-semibold ${isDone ? "bg-sage-deep text-white" : isNext ? "bg-ink text-white" : "border border-rule-strong text-ink-3"}`}
                >
                  {isDone ? <Check className="size-4" aria-hidden /> : i + 1}
                </span>
                <span className={`text-sm font-semibold ${isDone ? "text-ink-2" : "text-ink"}`}>{s.title}</span>
              </span>
              <span className="mt-2 flex-1 text-meta text-ink-3">{s.why}</span>
              <span className="mt-3">
                {isDone ? (
                  <span className="text-meta font-medium text-sage-deep">Done</span>
                ) : waits ? (
                  <span className="flex items-center gap-1.5 text-meta text-ink-3">
                    <Lock className="size-3.5" aria-hidden />
                    After &ldquo;{waits.title.toLowerCase()}&rdquo;
                  </span>
                ) : !may(s.permission) ? (
                  <span className="text-meta text-ink-3">Your administrator does this</span>
                ) : (
                  <LinkButton href={s.href} size="sm" variant={isNext ? "primary" : "default"}>
                    {s.action}
                  </LinkButton>
                )}
                {s.optional && !isDone && <span className="ml-2 text-meta text-ink-3">Optional</span>}
              </span>
            </li>
          );
        })}
      </ol>
    </Sheet>
  );
}

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
          To {doing}, you need {missing.map((m) => m.says).join(", and ")} first.
        </h2>
        <p className="mt-1 text-sm text-ink-2">Make {missing.length === 1 ? "it" : "them"} now, and you&apos;ll come straight back here.</p>
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
                <span className="text-meta text-ink-3">Ask your administrator</span>
              )}
            </li>
          ))}
        </ol>
        <Link href="/" className="mt-5 inline-flex items-center gap-1 text-meta text-ink-3 hover:text-ink">
          See every setup step on Home
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
      <Empty icon={icon} title="Nothing matches" actions={<LinkButton href={clear}>Clear filters</LinkButton>}>
        Try other filters, or clear them to see everything.
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
        {title}: {body} It needs {missing.map((m) => m.says).join(", and ")}{may(first.step.permission) ? "; make it, and you'll come back to this." : ". Your administrator sets that up."}
      </Empty>
    );
  }
  return (
    <Empty icon={icon} title={title} actions={may(permission) ? <LinkButton href={href} variant="primary">{action}</LinkButton> : undefined}>
      {body}
    </Empty>
  );
}
