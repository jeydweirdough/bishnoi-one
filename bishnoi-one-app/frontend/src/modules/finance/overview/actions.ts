"use server";

import { load } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { OverviewData, PeriodKey } from "./types";

/** The Overview for another period. The API sends only what this person may see (app/overview.py). */
export async function overviewFor(period: PeriodKey): Promise<Result<OverviewData>> {
  return attempt(() => load<OverviewData>(`/finance/overview?period=${period}`));
}
