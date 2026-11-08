// The Overview's plain rules: wording, the layout's spans and the saved choice of cards. Nothing here
// touches the page, so it's tested on its own (tests/overview.test.mjs).

import type { CardKey } from "./types";

export const MAX_CARDS = 5;

const plural = (word: string) => (/[^aeiou]y$/.test(word) ? `${word.slice(0, -1)}ies` : `${word}s`);

/** "1 bill", "3 entries". */
export function pl(n: number, word: string): string {
  return `${n.toLocaleString("en-PH")} ${n === 1 ? word : plural(word)}`;
}

/** A chart label: ₱1.2M, ₱340K, ₱95, from centavos. The exact figure is on hover. */
export function short(centavos: number): string {
  const n = Math.abs(centavos) / 100;
  const sign = centavos < 0 ? "-" : "";
  if (n >= 1e6) return `${sign}₱${(n / 1e6).toFixed(1).replace(/\.0$/, "")}M`;
  if (n >= 1e3) return `${sign}₱${Math.round(n / 1e3)}K`;
  return `${sign}₱${Math.round(n)}`;
}

/** The card spans for a lead and this many cards: 4 columns, never a hole. c2 = 2 columns, c4 = all 4. */
export const LAYOUT: Record<number, string[]> = {
  0: ["c4"],
  1: ["c2", "c2"],
  2: ["c2", "c2", "c4"],
  3: ["c2", "c2", "c2", "c2"],
  4: ["c2", "c1", "c1", "c2", "c2"],
  5: ["c2", "c1", "c1", "c2", "c1", "c1"],
};

/** Where each card goes: a wide card takes a wide slot when there is one. */
export function place<T extends { wide: boolean }>(cards: T[]): { spans: string[]; lead: string; cards: T[] } {
  const layout = LAYOUT[cards.length];
  const spans = layout.slice(1);
  const slots: (T | null)[] = new Array(cards.length).fill(null);
  const wideFree = spans.flatMap((s, i) => (s === "c1" ? [] : [i]));
  const rest: T[] = [];
  for (const c of cards) {
    if (c.wide && wideFree.length) slots[wideFree.shift()!] = c;
    else rest.push(c);
  }
  for (let i = 0; i < slots.length; i++) if (!slots[i]) slots[i] = rest.shift()!;
  return { spans, lead: layout[0], cards: slots as T[] };
}

export const picksKey = (userId: string) => `finance-overview-picks:${userId}`;

/** A saved choice, kept only as far as this person may still see each card. */
export function cleanPicks(saved: unknown, allowed: CardKey[]): CardKey[] | null {
  if (!Array.isArray(saved)) return null;
  return saved.filter((k): k is CardKey => allowed.includes(k as CardKey)).slice(0, MAX_CARDS);
}

/** Saved choices read and written safely: the page works the same without browser storage. */
export function readPicks(userId: string, allowed: CardKey[]): CardKey[] | null {
  try {
    const text = window.localStorage.getItem(picksKey(userId));
    return text ? cleanPicks(JSON.parse(text), allowed) : null;
  } catch {
    return null;
  }
}

export function writePicks(userId: string, picks: CardKey[] | null): void {
  try {
    if (picks) window.localStorage.setItem(picksKey(userId), JSON.stringify(picks));
    else window.localStorage.removeItem(picksKey(userId));
  } catch {
    // Works without storage: the choice lasts until the page is left.
  }
}

export function agoText(seconds: number): string {
  if (seconds < 10) return "updated just now";
  if (seconds < 60) return `updated ${seconds} seconds ago`;
  const minutes = Math.floor(seconds / 60);
  return `updated ${minutes} minute${minutes === 1 ? "" : "s"} ago`;
}
