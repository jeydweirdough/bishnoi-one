import { ApiError, fetchFile } from "@/src/modules/finance/platform/lib/api";

export async function GET(request: Request) {
  const id = new URL(request.url).searchParams.get("id") ?? "";
  if (!id || !/^[a-zA-Z0-9_-]+$/.test(id)) {
    return new Response("Invalid scan id.", { status: 400, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
  try {
    const file = await fetchFile(`/finance/scans/${encodeURIComponent(id)}/file`);
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
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't load file.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
