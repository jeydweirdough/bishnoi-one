import { ApiError, enc, fetchFile } from "@/src/platform/lib/api";

// A proof photo or scan kept with a production run or a distribution. The browser never talks to the
// API, so it comes through here with the signed-in person's token; the API
// checks they may see promotional materials.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string; ref: string }> }) {
  const { id, ref } = await ctx.params;
  try {
    const file = await fetchFile(`/admin/materials/${enc(id)}/proofs/${enc(ref)}`);
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
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't open the proof.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
