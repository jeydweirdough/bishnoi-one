// One account's statement as a spreadsheet, for the page's dates (src/exports/download.ts).
import type { NextRequest } from "next/server";
import { download } from "@/src/exports/download";
import { enc } from "@/src/platform/lib/api";

export async function GET(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  return download(`/finance/exports/accounts/${enc(id)}/statement.csv`, request.nextUrl.search);
}
