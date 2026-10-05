// One list of fund requests as a spreadsheet, with the page's search (src/exports/download.ts).
import type { NextRequest } from "next/server";
import { download } from "@/src/exports/download";

export function GET(request: NextRequest) {
  return download("/finance/exports/funds.csv", request.nextUrl.search);
}
