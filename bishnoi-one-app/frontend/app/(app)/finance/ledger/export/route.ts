// The journal as a spreadsheet, with the page's filters (src/exports/download.ts).
import type { NextRequest } from "next/server";
import { download } from "@/src/modules/finance/exports/download";

export function GET(request: NextRequest) {
  return download("/finance/exports/journal.csv", request.nextUrl.search);
}
