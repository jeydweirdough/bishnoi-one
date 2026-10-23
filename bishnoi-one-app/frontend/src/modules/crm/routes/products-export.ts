import { ApiError, fetchFile } from "@/src/platform/lib/api";

// Products and their prices as a spreadsheet, through here with the signed-in
// person's token: the prices in it are the ones they see. The same columns
// Import prices reads, so it can be edited and brought back.
export async function GET(request: Request) {
  const format = new URL(request.url).searchParams.get("format") === "csv" ? "csv" : "xlsx";
  try {
    const file = await fetchFile(`/exports/products?format=${format}`);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "application/octet-stream",
        "Content-Disposition": file.headers.get("content-disposition") ?? `attachment; filename="products.${format}"`,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't make the file.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
