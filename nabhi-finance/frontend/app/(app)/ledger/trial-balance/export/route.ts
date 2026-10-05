// The trial balance as a spreadsheet, as of the page's day (src/exports/download.ts).
import type { NextRequest } from "next/server";
import { download } from "@/src/exports/download";

export function GET(request: NextRequest) {
  return download("/finance/exports/trial-balance.csv", request.nextUrl.search);
}
