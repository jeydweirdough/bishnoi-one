import type { NextRequest } from "next/server";
import { ApiError, enc, fetchFile } from "@/src/platform/lib/api";

// The retention list as a CSV download. Passed through from the API, which
// scopes it to what the signed-in person may see (their own customers, or
// the team with Reports access).
export async function GET(request: NextRequest) {
  const asked = request.nextUrl.searchParams;
  const view = asked.get("view") === "team" ? "team" : "mine";
  // A team only means something with the division it is in.
  const team = asked.get("team");
  const division = asked.get("division");
  const query = [`view=${view}`, division && `division=${enc(division)}`, team && `team=${enc(team)}`].filter(Boolean).join("&");
  try {
    const file = await fetchFile(`/retention/export?${query}`);
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
