import { ApiError, fetchFile } from "@/src/platform/lib/api";

// Hands over a spreadsheet the API made (backend app/routers/exports.py). The
// browser never talks to the API, so the file comes through here with the
// signed-in person's token, and with the same filters the page had.
export async function download(path: string, search: string): Promise<Response> {
  try {
    const file = await fetchFile(`${path}${search}`);
    return new Response(file.body, {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": file.headers.get("content-disposition") ?? "attachment",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't make the file. Try again.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
