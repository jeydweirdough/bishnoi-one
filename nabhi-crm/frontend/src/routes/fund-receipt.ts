import { ApiError, enc, fetchFile } from "@/src/platform/lib/api";

// Opens a fund request's receipt. Finance keeps the file; the API fetches it
// from there once it has checked this person can see the request, and it
// comes through here with their token, as a quote's letter does.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string; expense: string }> }) {
  const { id, expense } = await ctx.params;
  try {
    const file = await fetchFile(`/funds/${enc(id)}/expenses/${enc(expense)}/receipt`);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "application/octet-stream",
        "Content-Disposition": file.headers.get("content-disposition") ?? "inline",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't open the receipt.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
