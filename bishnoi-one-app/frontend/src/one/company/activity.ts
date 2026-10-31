import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { accountSend, getAccount } from "@/src/platform/lib/account";
import { ApiError, apiFor } from "@/src/platform/lib/api";
import { enterSoftly } from "@/src/platform/lib/enter";
import { moduleByAppKey, type ModuleDef, type ModuleKey } from "@/src/platform/lib/modules";
import { moduleCookie } from "@/src/platform/lib/session-cookie";
import type { ActivityEntry } from "./types";

// The company's one activity log (2026-10-31): Bishnoi One's own (sign-ins, people, roles, the company) and each
// app's (who changed which record), read here by the company's administrators instead of in each app. Newest
// first across all of them; each source keeps its own place for "Older" (Bishnoi One by time, an app by entry).

export const PLATFORM = "platform";
const PAGE = 50;

export type LogEntry = ActivityEntry & { source: string; cursor: string };
export type LogSource = { key: string; label: string };

type AppItem = { id: number; at: string; actor: string; action: string; target: string | null; fields?: string[] };

/** Bishnoi One, then each app the company has that keeps a log of its own. */
export async function logSources(): Promise<(LogSource & { module: ModuleDef | null })[]> {
  const account = await getAccount();
  const apps = new Map<string, ModuleDef>();
  for (const a of account.apps) {
    const m = moduleByAppKey(a.key);
    if (m && m.status === "live" && !m.accountOnly) apps.set(m.key, m);
  }
  return [{ key: PLATFORM, label: "Bishnoi One", module: null }, ...[...apps.values()].map((m) => ({ key: m.key, label: m.label, module: m }))];
}

/**
 * One page of the log from `sources`, newest first. `before` is each source's place ("Older"); `q` and
 * `category` narrow Bishnoi One's entries. A source whose app can't be read now (not reachable, its session
 * not opened) is named in `unavailable` and left out, never the whole page.
 */
export async function readLog({ sources, before, q, category, here, skip }: {
  sources: (LogSource & { module: ModuleDef | null })[];
  before: Record<string, string>;
  q: string;
  category: string;
  /** This page's address, to come back to after opening an app's session. */
  here: string;
  /** Apps the enter route already said can't be opened. */
  skip: Set<string>;
}): Promise<{ entries: LogEntry[]; more: boolean; next: Record<string, string>; unavailable: string[] }> {
  const jar = await cookies();
  const unavailable: string[] = [];
  const read = sources.map(async (s): Promise<{ key: string; items: LogEntry[]; more: boolean }> => {
    if (s.module === null) {
      const p = new URLSearchParams({ ...(q && { q }), ...(category && { category }), ...(before[s.key] && { before: before[s.key] }) });
      const data = await accountSend<{ entries: ActivityEntry[]; more: boolean }>("GET", `/identity/company/activity?${p}`);
      return { key: s.key, items: data.entries.map((e) => ({ ...e, source: s.key, cursor: e.at })), more: data.more };
    }
    if (skip.has(s.key)) {
      unavailable.push(s.label);
      return { key: s.key, items: [], more: false };
    }
    // Its session first, softly: if it can't be opened, the page comes back with it in `unavailable`.
    if (!jar.get(moduleCookie(s.module.key))?.value) redirect(enterSoftly(s.module.key, here));
    try {
      const data = await apiFor(s.module.key as ModuleKey).get<{ items: AppItem[]; more: boolean }>(`/admin/audit?limit=${PAGE}${before[s.key] ? `&before=${before[s.key]}` : ""}`);
      const items = data.items.map((e) => ({
        id: `${s.key}-${e.id}`, at: e.at, actor: e.actor, action: e.action, category: "app", target: e.target ?? "", fields: e.fields ?? [], source: s.key, cursor: String(e.id),
      }));
      return { key: s.key, items, more: data.more };
    } catch (error) {
      if (!(error instanceof ApiError)) throw error;
      unavailable.push(s.label);
      return { key: s.key, items: [], more: false };
    }
  });
  const pages = await Promise.all(read);
  const all = pages.flatMap((p) => p.items).sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
  const entries = all.slice(0, PAGE);
  const next: Record<string, string> = { ...before };
  for (const p of pages) {
    const shown = entries.filter((e) => e.source === p.key);
    if (shown.length) next[p.key] = shown[shown.length - 1].cursor;
  }
  const more = all.length > entries.length || pages.some((p) => p.more);
  return { entries, more, next, unavailable };
}
