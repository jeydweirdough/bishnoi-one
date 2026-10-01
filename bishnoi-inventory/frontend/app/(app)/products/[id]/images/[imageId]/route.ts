import { ApiError, enc, fetchFile } from "@/src/platform/lib/api";

// A product's picture. The browser never talks to the API, so it comes
// through here with the signed-in person's token.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string; imageId: string }> }) {
  const { id, imageId } = await ctx.params;
  try {
    const file = await fetchFile(`/inventory/products/${enc(id)}/images/${enc(imageId)}`);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "image/webp",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    return new Response(null, { status });
  }
}
