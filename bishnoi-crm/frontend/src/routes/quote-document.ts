import { ApiError, enc, fetchFile } from "@/src/platform/lib/api";

// Opens a document the customer attached to a quote (an order link's: a valid ID...). As
// with the guarantee letter, the file comes through here with the signed-in
// person's token; the API checks they can see the quote before sending a byte.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string; n: string }> }) {
  const { id, n } = await ctx.params;
  if (!/^\d{1,2}$/.test(n)) return new Response("No such document.", { status: 404, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  try {
    const file = await fetchFile(`/quotes/${enc(id)}/documents/${n}`);
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
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't open the document.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
