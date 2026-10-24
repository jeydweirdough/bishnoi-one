import { ApiError, fetchFile } from "@/src/modules/finance/platform/lib/api";

// A BIR book or summary list as a CSV file. The browser never talks to the API,
// so the file comes through here with the signed-in person's token. Only
// Finance's /finance/bir reports, and only as CSV.
export async function GET(request: Request) {
  const asked = new URL(request.url).searchParams.get("path") ?? "";
  const target = new URL(asked, "http://report.local");
  if (target.origin !== "http://report.local" || !target.pathname.startsWith("/finance/bir/")) {
    return new Response("That isn't a BIR report.", { status: 400, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
  target.searchParams.set("format", "csv");
  try {
    const file = await fetchFile(`${target.pathname}${target.search}`);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "text/csv; charset=utf-8",
        "Content-Disposition": file.headers.get("content-disposition") ?? 'attachment; filename="report.csv"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't make the file.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
