"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { WaitingPrice } from "./types";

// Finance's decisions on what waits in the CRM. The API passes them on, under
// the person's name; the CRM keeps them (app/routers/prices.py).

type Decision = { decision: "approve" | "reject"; reason: string | null };

export async function decidePrice(p: WaitingPrice, { decision, reason }: Decision): Promise<Result<{ ok: boolean }>> {
  return attempt(async () => {
    const done = await api.post<{ ok: boolean }>("/finance/prices/decide", {
      kind: p.kind,
      productId: p.productId,
      priceTypeCode: p.priceTypeCode,
      teamId: p.teamId,
      decision,
      reason,
      label: `${p.productName}, ${p.priceTypeName}, ${p.teamName}`,
    });
    refresh();
    return done;
  });
}

export async function decideQuote(id: string, number: string, { decision, reason }: Decision): Promise<Result<{ ok: boolean }>> {
  return attempt(async () => {
    const done = await api.post<{ ok: boolean }>(`/finance/prices/quotes/${enc(id)}/decide`, { decision, note: reason, number });
    refresh();
    return done;
  });
}
