import { ApiError, fetchFile } from "@/src/modules/finance/platform/lib/api";

// Fixed report target only: no arbitrary upstream path or filing action.
export async function GET(request: Request) {
  const asked = new URL(request.url).searchParams;
  const year = asked.get("year") ?? "";
  const quarter = asked.get("quarter") ?? "";
  const rateBp = asked.get("rateBp") ?? "2500";
  if (!/^\d{4}$/.test(year) || !/^[1-3]$/.test(quarter) || !/^(2000|2500)$/.test(rateBp)) {
    return new Response("Choose a valid year, quarter (1-3), and tax rate.", { status: 400 });
  }
  try {
    const file = await fetchFile(`/finance/bir/returns/income-tax/draft.pdf?${new URLSearchParams({ year, quarter, rateBp })}`);
    return new Response(file.body, {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="1702Q-review-draft-${year}-Q${quarter}.pdf"`,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't make the review PDF.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "private, no-store" } });
  }
}
