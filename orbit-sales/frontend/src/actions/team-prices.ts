"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { TeamPriceInput, TeamPrices } from "@/src/platform/lib/types";

// Prices: what one team charges over the company's price
// list. The API checks on every one of these that the caller may price that
// team, and writes each change to the audit log.

const sheetPath = (division: string, team: string, part = "") =>
  `/sales/prices${part}?division=${enc(division)}&team=${enc(team)}`;

/** One team's sheet. Only the team being looked at is fetched, so a division with many teams stays light. */
export async function loadTeamPrices(division: string, team: string): Promise<Result<TeamPrices>> {
  return attempt(() => api.get<TeamPrices>(sheetPath(division, team)));
}

/**
 * Saves whichever of the two the lead touched: the price types the team quotes
 * with, then its own amounts. Both answer with the whole sheet, so the screen
 * ends up showing exactly what the API now holds.
 */
export async function saveTeamPrices(
  division: string,
  team: string,
  changes: { codes?: string[]; items?: TeamPriceInput[] },
): Promise<Result<TeamPrices>> {
  return attempt(async () => {
    let sheet: TeamPrices | null = null;
    if (changes.codes) sheet = await api.put<TeamPrices>(sheetPath(division, team, "/types"), { codes: changes.codes });
    if (changes.items?.length) sheet = await api.put<TeamPrices>(sheetPath(division, team), { items: changes.items });
    // Reps quote from these, so anything else this session has open should agree.
    refresh();
    return sheet ?? (await api.get<TeamPrices>(sheetPath(division, team)));
  });
}
