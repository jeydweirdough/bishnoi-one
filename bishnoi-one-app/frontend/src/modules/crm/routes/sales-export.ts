import type { NextRequest } from "next/server";
import { ApiError, enc, fetchFile } from "@/src/platform/lib/api";

// A sales results table as a CSV download. Passed through from the API, which
// scopes it to what the signed-in person may see (their own results, or
// everyone their role reaches, with Reports → Export).
const REPORTS = new Set(["people", "teams", "customers", "products"]);

export async function GET(request: NextRequest) {
  const asked = request.nextUrl.searchParams;
  const report = REPORTS.has(asked.get("report") ?? "") ? asked.get("report")! : "people";
  const view = asked.get("view") === "team" ? "team" : "mine";
  const period = asked.get("period");
  const team = asked.get("team");
  const query = [`report=${report}`, `view=${view}`, period && `period=${enc(period)}`, team && `team=${enc(team)}`].filter(Boolean).join("&");
  try {
    const file = await fetchFile(`/sales/results/export?${query}`);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "text/csv; charset=utf-8",
        "Content-Disposition": file.headers.get("content-disposition") ?? "attachment",
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't make the export.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
