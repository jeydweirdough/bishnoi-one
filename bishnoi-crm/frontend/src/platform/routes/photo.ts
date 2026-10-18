import { ApiError, enc, fetchFile } from "../lib/api";

// A colleague's picture. The browser never talks to the API, so it comes
// through here with the signed-in person's token; the API only sends a picture
// of someone in the same company. Nothing is returned when they have none —
// the screens draw their initials instead.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const file = await fetchFile(`/people/${enc(id)}/photo`);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "image/webp",
        "X-Content-Type-Options": "nosniff",
        // Their own browser may keep it briefly; nothing in between may.
        "Cache-Control": "private, max-age=300",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    return new Response(null, { status: status === 404 ? 404 : status });
  }
}
