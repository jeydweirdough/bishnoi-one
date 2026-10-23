import { ApiError, enc, fetchFile } from "@/src/modules/finance/platform/lib/api";

// Opens a receipt. The browser never talks to the API, so the file comes
// through here with the signed-in person's token.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string; expense: string }> }) {
  const { id, expense } = await ctx.params;
  try {
    const file = await fetchFile(`/finance/funds/${enc(id)}/expenses/${enc(expense)}/receipt`);
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
