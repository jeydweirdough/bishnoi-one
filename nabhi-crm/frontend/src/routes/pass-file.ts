import { ApiError, fetchFile } from "@/src/platform/lib/api";

/** A file from the API, passed through with the person's token (which never reaches the browser). */
export async function passFile(path: string, fallback: string, disposition = "inline") {
  try {
    const file = await fetchFile(path);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "application/octet-stream",
        "Content-Disposition": file.headers.get("content-disposition") ?? disposition,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": file.headers.get("cache-control") ?? "private, no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : fallback;
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
