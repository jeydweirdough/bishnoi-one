"use client";

import { X } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { plural } from "../lib/format";
import type { Job } from "../lib/types";

// Picking several records and acting on them at once, the way a mail app does:
// tick rows, a bar rises from the bottom with what can be done to them, and the
// outcome comes back as one message. The page renders the rows; this holds
// which are ticked. Pages give the provider a `key` that changes with their
// filters, so a new list never inherits ticks for rows it no longer shows.

type Item = { id: string; name: string };
type Result<T> = { ok: true; data: T } | { ok: false; error: string };

type Selection = {
  /** False until "Select" is pressed, on lists where rows have their own tap (follow-ups' done tick). */
  selecting: boolean;
  setSelecting: (on: boolean) => void;
  ids: string[];
  names: ReadonlyMap<string, string>;
  isSelected: (id: string) => boolean;
  toggle: (id: string) => void;
  /** Ticks every row on this page that can be ticked, or none. */
  setPage: (on: boolean) => void;
  pageState: "none" | "some" | "all";
  /** Beyond this page: every record the filters find (customers). */
  matching: Item[] | null;
  selectMatching: (items: Item[]) => void;
  keepOnly: (ids: string[]) => void;
  clear: () => void;
  busy: ReadonlySet<string>;
  setBusy: (ids: string[]) => void;
};

const SelectionContext = createContext<Selection | null>(null);

export function SelectionProvider({
  items,
  toggled = false,
  children,
}: {
  /** The rows that can be ticked, in page order. */
  items: Item[];
  /** True where selecting is a mode entered with a "Select" button. */
  toggled?: boolean;
  children: ReactNode;
}) {
  const [selecting, setSelecting] = useState(!toggled);
  const [picked, setPicked] = useState<string[]>([]);
  const [matching, setMatching] = useState<Item[] | null>(null);
  const [busy, setBusyState] = useState<ReadonlySet<string>>(new Set());

  const value = useMemo<Selection>(() => {
    const onPage = new Set(items.map((i) => i.id));
    // Only what's on screen can be acted on, unless "all that match" was asked for.
    const ids = matching ? matching.map((i) => i.id) : picked.filter((id) => onPage.has(id));
    const chosen = new Set(ids);
    const names = new Map([...items, ...(matching ?? [])].map((i) => [i.id, i.name]));
    const onPageChosen = items.filter((i) => chosen.has(i.id)).length;
    return {
      selecting,
      setSelecting: (on) => {
        setSelecting(on || !toggled);
        if (!on) {
          setPicked([]);
          setMatching(null);
        }
      },
      ids,
      names,
      isSelected: (id) => chosen.has(id),
      toggle: (id) => {
        if (matching) {
          // Unticking one of "all that match" drops back to this page, less that one.
          setMatching(null);
          setPicked(items.map((i) => i.id).filter((x) => x !== id));
          return;
        }
        setPicked((now) => (now.includes(id) ? now.filter((x) => x !== id) : [...now, id]));
      },
      setPage: (on) => {
        setMatching(null);
        setPicked(on ? items.map((i) => i.id) : []);
      },
      pageState: onPageChosen === 0 ? "none" : onPageChosen === items.length ? "all" : "some",
      matching,
      selectMatching: (found) => setMatching(found),
      keepOnly: (keep) => {
        setMatching(null);
        setPicked(keep.filter((id) => onPage.has(id)));
      },
      clear: () => {
        setMatching(null);
        setPicked([]);
      },
      busy,
      setBusy: (ids) => setBusyState(new Set(ids)),
    };
  }, [items, picked, matching, busy, selecting, toggled]);

  return <SelectionContext value={value}>{children}</SelectionContext>;
}

/** The selection, or null outside a provider (a row that's also used on pages without bulk actions). */
export function useSelectionMaybe(): Selection | null {
  return useContext(SelectionContext);
}

export function useSelection(): Selection {
  const selection = useContext(SelectionContext);
  if (!selection) throw new Error("useSelection needs a SelectionProvider");
  return selection;
}

// --- ticking -----------------------------------------------------------------------

/** A row's tick. 16px to look at; the label around it makes it 40px to hit. */
export function SelectBox({ id, label }: { id: string; label: string }) {
  const s = useSelection();
  if (!s.selecting) return null;
  return (
    <label className="relative z-10 -m-3 inline-flex cursor-pointer p-3">
      <input
        type="checkbox"
        checked={s.isSelected(id)}
        onChange={() => s.toggle(id)}
        disabled={s.busy.size > 0}
        aria-label={`Select ${label}`}
        className="size-4 cursor-pointer accent-hema disabled:cursor-not-allowed"
      />
    </label>
  );
}

/** The tick above a list: all of this page, none, or (dashed) some. With children, they're its visible label. */
export function SelectAllBox({ label = "Select all on this page", children }: { label?: string; children?: ReactNode }) {
  const s = useSelection();
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (box.current) box.current.indeterminate = s.pageState === "some";
  }, [s.pageState]);
  if (!s.selecting) return null;
  return (
    <label className={`relative z-10 inline-flex cursor-pointer items-center gap-3 ${children ? "py-2" : "-m-3 p-3"}`}>
      <input
        ref={box}
        type="checkbox"
        checked={s.pageState === "all"}
        onChange={() => s.setPage(s.pageState !== "all")}
        disabled={s.busy.size > 0}
        aria-label={children ? undefined : label}
        className="size-4 cursor-pointer accent-hema disabled:cursor-not-allowed"
      />
      {children}
    </label>
  );
}

/** A row that tints when ticked and dims while a bulk action is working on it. */
export function SelectableRow({
  id,
  as: Tag = "tr",
  className = "",
  children,
}: {
  id: string;
  as?: "tr" | "li";
  className?: string;
  children: ReactNode;
}) {
  const s = useSelectionMaybe();
  const selected = s?.isSelected(id) ?? false;
  const busy = s?.busy.has(id) ?? false;
  return (
    <Tag
      data-selected={selected || undefined}
      aria-busy={busy || undefined}
      className={`${className} transition-opacity ${selected ? "bg-hema-tint/60" : ""} ${busy ? "opacity-45" : ""}`}
    >
      {children}
    </Tag>
  );
}

/** "Select" / "Cancel", as in a phone's mail app, for lists where selecting is a mode. */
export function SelectToggle() {
  const s = useSelection();
  return (
    <Button size="sm" variant={s.selecting ? "quiet" : "default"} onClick={() => s.setSelecting(!s.selecting)} aria-pressed={s.selecting}>
      {s.selecting ? "Cancel" : "Select"}
    </Button>
  );
}

// --- the bar ----------------------------------------------------------------------------

/**
 * Rises under the list once something is ticked: how many, then what can be done
 * to them. `step` replaces the actions while one asks for a detail (a date, a
 * person), so the question appears where the choice was made.
 */
export function BulkBar({
  noun,
  children,
  step,
  extra,
}: {
  noun: [string, string];
  children: ReactNode;
  step?: ReactNode;
  extra?: ReactNode;
}) {
  const s = useSelection();
  const count = s.ids.length;
  if (!s.selecting || count === 0) return null;
  return (
    <div
      role="region"
      aria-label="Bulk actions"
      className="sticky bottom-3 z-20 mt-3 flex animate-rise flex-wrap items-center gap-x-4 gap-y-3 rounded-[18px] bg-sheet px-4 py-3 shadow-overlay"
    >
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
        <p aria-live="polite" className="font-semibold">
          {plural(count, noun[0], noun[1])} selected
        </p>
        {extra}
      </div>
      <div className="ml-auto flex flex-wrap items-end gap-2">
        {step ?? (
          <>
            {children}
            <Button size="sm" variant="quiet" onClick={s.clear} disabled={s.busy.size > 0} icon={<X className="size-4" aria-hidden />}>
              Clear
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

/** One question inside the bar: its fields, then the button that does it. */
export function BulkStep({
  submitLabel,
  danger = false,
  onSubmit,
  onCancel,
  children,
}: {
  submitLabel: string;
  danger?: boolean;
  /** Return false to stay on the step (say, when a field is missing). */
  onSubmit: (form: FormData) => Promise<boolean | void>;
  onCancel: () => void;
  children: ReactNode;
}) {
  const [pending, setPending] = useState(false);
  return (
    <form
      className="flex animate-reshape flex-wrap items-end gap-x-3 gap-y-2"
      onSubmit={async (event) => {
        event.preventDefault();
        setPending(true);
        const done = await onSubmit(new FormData(event.currentTarget));
        setPending(false);
        if (done !== false) onCancel();
      }}
      onKeyDown={(event) => event.key === "Escape" && !pending && onCancel()}
    >
      {children}
      <Button type="submit" size="sm" variant={danger ? "danger" : "primary"} loading={pending}>
        {submitLabel}
      </Button>
      <Button size="sm" variant="quiet" onClick={onCancel} disabled={pending}>
        Back
      </Button>
    </form>
  );
}

// --- running one ---------------------------------------------------------------------

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Follows a queued job through /jobs/[id] until it's done; null when it can't be followed. */
async function follow(job: Job, onProgress: (job: Job) => void): Promise<Job | null> {
  let misses = 0;
  while (job.status !== "done") {
    onProgress(job);
    await pause(job.status === "queued" ? 1000 : 700);
    try {
      const response = await fetch(`/jobs/${encodeURIComponent(job.id)}`, { cache: "no-store" });
      if (response.ok) {
        job = (await response.json()) as Job;
        misses = 0;
        continue;
      }
      if (response.status === 401 || response.status === 404) return null;
    } catch {
      // a blip: try again
    }
    if (++misses >= 5) return null;
  }
  return job;
}

export type Wording = {
  /** "Marking done", while it runs. */
  doing: string;
  /** "3 follow-ups marked done", when it has. */
  did: (n: number) => string;
};

/**
 * Runs a bulk action on what's ticked and reports back in one toast: progress
 * while the API works through a queued job, then what was done and, by name,
 * what wasn't. The ones that weren't stay ticked, ready for another go.
 */
export function useBulkRun() {
  const s = useSelection();
  const router = useRouter();
  const [running, setRunning] = useState(false);

  const run = useCallback(
    async (wording: Wording, submit: (ids: string[]) => Promise<Result<Job>>): Promise<boolean> => {
      const ids = s.ids;
      const names = s.names;
      if (!ids.length) return false;
      setRunning(true);
      s.setBusy(ids);
      const toastId = toast.loading(`${wording.doing}…`);
      try {
        const result = await submit(ids);
        if (!result.ok) {
          toast.error(result.error, { id: toastId });
          return false;
        }
        const queued = result.data.status !== "done";
        const job = await follow(result.data, (j) =>
          toast.loading(`${wording.doing}: ${j.processed} of ${j.total}`, { id: toastId }),
        );
        if (queued) router.refresh();
        if (!job) {
          toast.info("Still working on it in the background", {
            id: toastId,
            description: "Reload in a minute to see the changes.",
          });
          s.clear();
          return true;
        }
        report(job, wording, names, toastId);
        s.keepOnly(job.failures.map((f) => f.id));
        if (job.failed === 0) s.setSelecting(false);
        return true;
      } finally {
        s.setBusy([]);
        setRunning(false);
      }
    },
    [s, router],
  );

  return { run, running };
}

function report(job: Job, wording: Wording, names: ReadonlyMap<string, string>, toastId: string | number) {
  if (job.failed === 0) {
    toast.success(wording.did(job.succeeded), { id: toastId });
    return;
  }
  const shown = job.failures.slice(0, 3).map((f) => `${names.get(f.id) ?? "One of them"}: ${f.error}`);
  const more = job.failed - shown.length;
  const title = job.succeeded ? `${wording.did(job.succeeded)}. ${job.failed} couldn't be.` : `None could be done.`;
  toast.warning(title, {
    id: toastId,
    description: [...shown, more > 0 ? `…and ${more} more. They're still ticked.` : "They're still ticked."].join("\n"),
    duration: 12_000,
    classNames: { description: "whitespace-pre-line" },
  });
}
