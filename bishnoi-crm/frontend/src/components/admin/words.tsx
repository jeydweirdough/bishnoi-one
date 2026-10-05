import { Empty, Sheet } from "@/src/platform/ui/sheet";
import type { Scope } from "@/src/platform/lib/types";

/** Whose records a role reaches, said as a sentence ending. */
export const SCOPE_WORDS: Record<Scope, string> = {
  own: "Reaches their own records.",
  team: "Reaches their team's records.",
  managed: "Reaches the records of every team they manage.",
  all: "Reaches every record.",
};

/** Whose records a role reaches, as a short tag. */
export const SCOPE_TAGS: Record<Scope, string> = { own: "Own records", team: "Team's records", managed: "Managed teams' records", all: "All records" };

/** For an Administration page someone's role doesn't open. */
export function NoAccess({ what }: { what: string }) {
  return (
    <Sheet>
      <Empty icon="roles" title={`Your role doesn't include ${what}`}>
        Ask an administrator if you need it.
      </Empty>
    </Sheet>
  );
}

/** "Switched off", the same mark everywhere. */
export function OffTag({ children = "Switched off" }: { children?: string }) {
  return (
    <span className="inline-flex h-5 items-center rounded-[4px] border border-rule-strong px-1.5 text-stamp text-ink-3 uppercase">
      {children}
    </span>
  );
}
