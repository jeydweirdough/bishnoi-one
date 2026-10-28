"use client";

import {
  ChartColumn,
  Clock,
  FolderOpen,
  LayoutGrid,
  Lock,
  Plus,
  Search,
  Share2,
  SlidersHorizontal,
  Star,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { CreateReportModal } from "./create-report-modal";
import { deleteReport } from "./custom-actions";
import type { SavedReport } from "./custom";
import type { ReportInfo } from "./types";

/**
 * A module's Reports Center (decided 2026-10-26, past Zoho's): categories down the side with their
 * counts, then Favourites, Recently viewed, My Reports and Shared Reports; one list on the
 * right, searched across names and what each report is for ("/" jumps to the search), each row a
 * star to keep it, its name and purpose, its category and when you last opened it.
 */

type View =
  | "all"
  | "favourites"
  | "recent"
  | "mine"
  | "shared"
  | { group: string };
type Memory = { favourites: string[]; seen: Record<string, string> };

type IndexItem = {
  key: string;
  title: string;
  about: string;
  group: string;
  href: string;
  fixed?: boolean;
  isCustom?: boolean;
  mine?: boolean;
  shared?: boolean;
  owner?: string;
  updatedAt?: string | null;
  saved?: SavedReport;
};

const storeKey = (base: string) => `bishnoi-reports:${base}`;

export function readMemory(base: string): Memory {
  try {
    const m = JSON.parse(localStorage.getItem(storeKey(base)) ?? "{}");
    return {
      favourites: Array.isArray(m.favourites) ? m.favourites : [],
      seen: m.seen && typeof m.seen === "object" ? m.seen : {},
    };
  } catch {
    return { favourites: [], seen: {} };
  }
}

export function writeMemory(base: string, m: Memory) {
  try {
    localStorage.setItem(storeKey(base), JSON.stringify(m));
  } catch {
    // private window or full: favourites just don't stick
  }
}

/** Notes that a report was opened, for Recently viewed and Last viewed. */
export function RememberReport({
  base,
  reportKey,
}: {
  base: string;
  reportKey: string;
}) {
  useEffect(() => {
    const m = readMemory(base);
    writeMemory(base, {
      ...m,
      seen: { ...m.seen, [reportKey]: new Date().toISOString() },
    });
  }, [base, reportKey]);
  return null;
}

function ago(iso: string | undefined | null): string {
  if (!iso) return "—";
  const mins = Math.round((Date.now() - Date.parse(iso)) / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} d ago`;
  return new Date(iso).toLocaleDateString("en", {
    month: "short",
    day: "numeric",
  });
}

export function ReportsIndex({
  reports,
  base,
  group,
  savedReports = [],
}: {
  reports: ReportInfo[];
  base: string;
  group?: string;
  savedReports?: SavedReport[];
}) {
  const router = useRouter();
  const [isCreating, setIsCreating] = useState(false);
  const [isDeleting, startDeleteTransition] = useTransition();
  const app = base.split("/").filter(Boolean)[0] ?? "crm";

  const groups = useMemo(
    () => [...new Set(reports.map((r) => r.group))],
    [reports],
  );
  const [view, setView] = useState<View>(
    group && groups.includes(group) ? { group } : "all",
  );
  const [q, setQ] = useState("");
  const [memory, setMemory] = useState<Memory>({ favourites: [], seen: {} });
  const search = useRef<HTMLInputElement>(null);

  function handleDelete(id: string, name: string) {
    if (!window.confirm(`Are you sure you want to delete the custom report "${name}"?`)) return;
    startDeleteTransition(async () => {
      const res = await deleteReport(id);
      if (!res.ok) {
        toast.error(res.error);
        return;
      }
      toast.success("Custom report deleted");
      router.refresh();
    });
  }

  useEffect(() => setMemory(readMemory(base)), [base]);
  useEffect(
    () => setView(group && groups.includes(group) ? { group } : "all"),
    [group, groups],
  );
  useEffect(() => {
    const jump = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (
        e.key === "/" &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) &&
        !t.isContentEditable
      ) {
        e.preventDefault();
        search.current?.focus();
      }
    };
    document.addEventListener("keydown", jump);
    return () => document.removeEventListener("keydown", jump);
  }, []);

  function choose(v: View) {
    setView(v);
    const url =
      typeof v === "object"
        ? `${base}?group=${encodeURIComponent(v.group)}`
        : base;
    window.history.replaceState(null, "", url);
  }

  function star(key: string) {
    const favourites = memory.favourites.includes(key)
      ? memory.favourites.filter((k) => k !== key)
      : [...memory.favourites, key];
    const next = { ...memory, favourites };
    setMemory(next);
    writeMemory(base, next);
  }

  // Combine base reports and saved custom reports into unified items
  const allItems = useMemo<IndexItem[]>(() => {
    const baseItems: IndexItem[] = reports.map((r) => ({
      key: r.key,
      title: r.title,
      about: r.about,
      group: r.group,
      href: r.href ?? `${base}/${r.key}`,
      fixed: r.fixed,
      isCustom: false,
    }));

    const customItems: IndexItem[] = savedReports.map((s) => {
      const parent = reports.find((r) => r.key === s.baseKey);
      return {
        key: `saved-${s.id}`,
        title: s.name,
        about: `Custom report based on ${parent?.title ?? s.baseKey}${s.shared ? " · Shared with company" : ""}`,
        group: s.mine ? "My reports" : "Shared reports",
        href: `${base}/${s.baseKey}?saved=${encodeURIComponent(s.id)}`,
        isCustom: true,
        mine: s.mine,
        shared: s.shared,
        owner: s.owner,
        updatedAt: s.updatedAt,
        saved: s,
      };
    });

    return [...customItems, ...baseItems];
  }, [reports, savedReports, base]);

  const mySaved = useMemo(
    () => savedReports.filter((s) => s.mine),
    [savedReports],
  );
  const sharedSaved = useMemo(
    () => savedReports.filter((s) => s.shared && !s.mine),
    [savedReports],
  );

  const inView = useMemo(() => {
    if (view === "favourites")
      return allItems.filter((r) => memory.favourites.includes(r.key));
    if (view === "recent")
      return allItems
        .filter((r) => memory.seen[r.key])
        .sort((a, b) =>
          (memory.seen[b.key] ?? "").localeCompare(memory.seen[a.key] ?? ""),
        );
    if (view === "mine") return allItems.filter((r) => r.isCustom && r.mine);
    if (view === "shared")
      return allItems.filter((r) => r.isCustom && r.shared && !r.mine);
    if (typeof view === "object")
      return allItems.filter((r) => r.group === view.group);
    return allItems;
  }, [view, allItems, memory]);

  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    return t
      ? inView.filter((r) =>
          `${r.title} ${r.about} ${r.group} ${r.owner ?? ""}`
            .toLowerCase()
            .includes(t),
        )
      : inView;
  }, [q, inView]);

  const title =
    view === "all"
      ? "All reports"
      : view === "favourites"
        ? "Favourites"
        : view === "recent"
          ? "Recently viewed"
          : view === "mine"
            ? "My custom reports"
            : view === "shared"
              ? "Shared reports"
              : `${view.group} reports`;

  const recentCount = allItems.filter((r) => memory.seen[r.key]).length;
  const isOn = (v: View) =>
    typeof v === "object" && typeof view === "object"
      ? v.group === view.group
      : v === view;

  const railItem = (
    v: View,
    label: string,
    count: number,
    icon: React.ReactNode,
  ) => (
    <button
      suppressHydrationWarning
      key={typeof v === "object" ? v.group : v}
      type="button"
      onClick={() => choose(v)}
      aria-current={isOn(v) ? "page" : undefined}
      className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors ${isOn(v) ? "bg-mint-2 font-semibold text-ink" : "text-ink-2 hover:bg-bench hover:text-ink"}`}
    >
      <span
        className={`inline-flex shrink-0 [&>svg]:size-4 ${isOn(v) ? "text-sage-deep" : "text-ink-3"}`}
        aria-hidden
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span className="text-meta text-ink-3 tabular-nums">{count}</span>
    </button>
  );

  return (
    <div className="grid gap-5 lg:grid-cols-[15rem_minmax(0,1fr)] lg:items-start">
      <nav
        aria-label="Report categories"
        className="rounded-2xl border border-rule bg-white p-2 lg:sticky lg:top-4"
      >
        {railItem("all", "All reports", allItems.length, <LayoutGrid />)}
        {railItem(
          "favourites",
          "Favourites",
          memory.favourites.filter((k) => allItems.some((r) => r.key === k))
            .length,
          <Star />,
        )}
        {railItem("recent", "Recently viewed", recentCount, <Clock />)}

        <p className="px-3 pt-3 pb-1 text-caps text-ink-3 uppercase">
          Custom reports
        </p>
        {railItem(
          "mine",
          "My reports",
          mySaved.length,
          <SlidersHorizontal />,
        )}
        {railItem(
          "shared",
          "Shared reports",
          sharedSaved.length,
          <Share2 />,
        )}

        <p className="px-3 pt-3 pb-1 text-caps text-ink-3 uppercase">
          Categories
        </p>
        {groups.map((g) =>
          railItem(
            { group: g },
            g,
            reports.filter((r) => r.group === g).length,
            <FolderOpen />,
          ),
        )}
      </nav>

      <section className="overflow-hidden rounded-2xl border border-rule bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-5 py-3">
          <h2 className="flex items-center gap-2 text-heading text-ink">
            {title}
            <span className="rounded-full bg-mint-2 px-2 text-meta font-semibold text-sage-deep tabular-nums">
              {shown.length}
            </span>
          </h2>
          <div className="flex items-center gap-3">
            <label className="relative w-full max-w-xs">
              <span className="sr-only">Search reports</span>
              <Search
                className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3"
                aria-hidden
              />
              <input
                ref={search}
                suppressHydrationWarning
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search reports"
                className="h-9 w-full rounded-lg border border-rule bg-bench pr-9 pl-9 text-sm outline-none focus:border-ink focus:bg-white"
              />
              <kbd className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rounded border border-rule bg-white px-1.5 text-[11px] text-ink-3">
                /
              </kbd>
            </label>
            <button
              type="button"
              onClick={() => setIsCreating(true)}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-ink px-3.5 text-sm font-semibold text-white shadow-xs hover:bg-ink/90 transition-colors shrink-0"
            >
              <Plus className="size-4" /> New Custom Report
            </button>
          </div>
        </div>

        {shown.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <ChartColumn className="mx-auto size-8 text-ink-3" aria-hidden />
            <p className="mt-2 font-semibold text-ink">
              {q
                ? `No report matches “${q}”`
                : view === "favourites"
                  ? "No favourites yet"
                  : view === "recent"
                    ? "Nothing opened yet"
                    : view === "mine"
                      ? "No custom reports yet"
                      : view === "shared"
                        ? "No shared reports from colleagues"
                        : "No reports here"}
            </p>
            <p className="mt-1 text-sm text-ink-3">
              {q
                ? "Try another word, or All reports."
                : view === "favourites"
                  ? "Tap the star beside a report to keep it here."
                  : view === "mine"
                    ? "Open any base report and click Customise report to build your own."
                    : view === "recent"
                      ? "Reports you open show up here."
                      : ""}
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-bench text-left text-meta text-ink-3">
              <tr>
                <th className="w-10 py-2.5 pl-4" aria-label="Favourite" />
                <th className="px-2 py-2.5 font-medium">Report</th>
                <th className="hidden px-3 py-2.5 font-medium md:table-cell">
                  Category
                </th>
                <th className="hidden px-5 py-2.5 text-right font-medium sm:table-cell">
                  {view === "mine" || view === "shared"
                    ? "Updated"
                    : "Last viewed"}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {shown.map((r) => {
                const fav = memory.favourites.includes(r.key);
                return (
                  <tr
                    key={r.key}
                    className="relative transition-colors hover:bg-mint/50 focus-within:bg-mint/50"
                  >
                    <td className="py-3 pl-4 align-top">
                      <button
                        suppressHydrationWarning
                        type="button"
                        onClick={() => star(r.key)}
                        aria-pressed={fav}
                        aria-label={
                          fav
                            ? `Remove ${r.title} from favourites`
                            : `Add ${r.title} to favourites`
                        }
                        title={fav ? "In favourites" : "Add to favourites"}
                        className="relative z-[1] grid size-7 place-items-center rounded-md hover:bg-white"
                      >
                        <Star
                          className={`size-4 ${fav ? "fill-[#f5b301] text-[#f5b301]" : "text-ink-3"}`}
                          aria-hidden
                        />
                      </button>
                    </td>
                    <td className="px-2 py-3">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <Link
                          href={r.href}
                          className="font-medium text-ink outline-none after:absolute after:inset-0 hover:underline focus-visible:underline"
                        >
                          {r.title}
                        </Link>
                        {r.fixed && (
                          <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 py-0.2 text-[10px] font-semibold text-amber-800 border border-amber-200">
                            <Lock className="size-2.5" /> Fixed
                          </span>
                        )}
                        {r.isCustom && (
                          <span className="inline-flex items-center gap-1 rounded bg-mint-2 px-1.5 py-0.2 text-[10px] font-semibold text-sage-deep">
                            Custom
                          </span>
                        )}
                        {r.isCustom && !r.mine && r.owner && (
                          <span className="text-meta text-ink-3">
                            by {r.owner}
                          </span>
                        )}
                      </div>
                      <span className="mt-0.5 block text-meta text-ink-3">
                        {r.about}
                      </span>
                    </td>
                    <td className="hidden px-3 py-3 align-top md:table-cell">
                      <span className="inline-flex rounded-md bg-bench px-2 py-0.5 text-meta text-ink-2">
                        {r.group}
                      </span>
                    </td>
                    <td className="hidden px-5 py-3 text-right align-top text-meta whitespace-nowrap text-ink-3 sm:table-cell">
                      <div className="flex items-center justify-end gap-2">
                        <span>{ago(r.updatedAt ?? memory.seen[r.key])}</span>
                        {r.isCustom && r.mine && r.saved && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              handleDelete(r.saved!.id, r.title);
                            }}
                            className="relative z-[2] grid size-6 place-items-center rounded text-ink-3 hover:bg-rose-50 hover:text-rose-600 transition-colors"
                            title="Delete custom report"
                          >
                            <Trash2 className="size-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <CreateReportModal
        open={isCreating}
        onClose={() => setIsCreating(false)}
        reports={reports}
        baseAddress={base}
        app={app}
      />
    </div>
  );
}
