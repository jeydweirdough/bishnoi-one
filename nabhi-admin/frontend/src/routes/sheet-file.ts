import { ApiError, enc, fetchFile } from "@/src/platform/lib/api";

// Excel reports and import templates. The API builds the workbook once it has
// checked this person's role; it comes through here with their token, so the
// token never reaches the browser.
async function pass(path: string) {
  try {
    const file = await fetchFile(path);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "application/octet-stream",
        "Content-Disposition": file.headers.get("content-disposition") ?? "attachment",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't prepare the file.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}

type Ctx = { params: Promise<{ kind: string }> };

export async function report(_request: Request, ctx: Ctx) {
  const { kind } = await ctx.params;
  return pass(`/admin/reports/${enc(kind)}`);
}

export async function template(_request: Request, ctx: Ctx) {
  const { kind } = await ctx.params;
  return pass(`/admin/imports/${enc(kind)}/template`);
}
