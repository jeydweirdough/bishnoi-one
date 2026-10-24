import { ApiError, enc, fetchFile } from "@/src/modules/inventory/platform/lib/api";

// A report as a spreadsheet file, passed through from the API with the
// signed-in person's token (it checks they may export).
export async function GET(request: Request, ctx: { params: Promise<{ key: string }> }) {
  const { key } = await ctx.params;
  const search = new URL(request.url).search;
  try {
    const file = await fetchFile(`/inventory/reports/${enc(key)}/csv${search}`);
    return new Response(file.body, {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": file.headers.get("content-disposition") ?? `attachment; filename="${key}.csv"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "The report couldn't be exported.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
