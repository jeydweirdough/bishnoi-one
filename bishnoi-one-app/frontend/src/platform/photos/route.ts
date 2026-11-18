import { ApiError, enc, fetchFile } from "@/src/platform/lib/api";

// A photo kept with a record (a delivery, a package, a visit: Step 4B). The browser never talks to the API, so it
// comes through here with the signed-in person's token; the API checks they may see the record first.
export function photoRoute(apiPath: (id: string) => string) {
  return async function GET(_request: Request, ctx: { params: Promise<{ id: string }> }) {
    const { id } = await ctx.params;
    try {
      const file = await fetchFile(apiPath(enc(id)));
      return new Response(file.body, {
        headers: {
          "Content-Type": file.headers.get("content-type") ?? "image/jpeg",
          "Content-Disposition": "inline",
          "X-Content-Type-Options": "nosniff",
          "Cache-Control": "private, max-age=3600",
        },
      });
    } catch (error) {
      return new Response(null, { status: error instanceof ApiError ? error.status : 500 });
    }
  };
}
