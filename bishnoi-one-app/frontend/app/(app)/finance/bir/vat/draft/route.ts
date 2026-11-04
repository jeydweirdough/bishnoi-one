import { ApiError, fetchFile } from "@/src/modules/finance/platform/lib/api";

// Fixed report target only: no arbitrary upstream path or filing action.
export async function GET(request: Request) {
  const asked = new URL(request.url).searchParams;
  const year = asked.get("year") ?? "";
  const quarter = asked.get("quarter") ?? "";
  if (!/^\d{4}$/.test(year) || !/^[1-4]$/.test(quarter)) {
    return new Response("Choose a valid year and quarter.", { status: 400 });
  }
  try {
    const file = await fetchFile(`/finance/bir/returns/vat/draft.pdf?${new URLSearchParams({year,quarter})}`);
    return new Response(file.body, { headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": 'attachment; filename="2550Q-review-draft.pdf"',
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "private, no-store",
    }});
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't make the review PDF.";
    return new Response(message, { status, headers: {"Content-Type":"text/plain; charset=utf-8", "Cache-Control":"private, no-store"} });
  }
}
