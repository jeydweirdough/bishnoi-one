import { ApiError, enc, fetchFile } from "@/src/modules/inventory/platform/lib/api";

// A delivery's proof-of-delivery photo from the courier (step 12). The browser never talks to the API, so it
// comes through here with the signed-in person's token.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const file = await fetchFile(`/inventory/orders/${enc(id)}/delivery-photo`);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "image/jpeg",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    return new Response(null, { status });
  }
}
