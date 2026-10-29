import { ApiError, fetchFile } from "@/src/modules/finance/platform/lib/api";

export async function GET(request: Request) {
  const asked = new URL(request.url).searchParams;
  const query = new URLSearchParams({ format: "csv" });
  for (const key of ["supplierId", "bucket", "asOf"]) if (asked.get(key)) query.set(key, asked.get(key)!);
  try {
    const file = await fetchFile(`/finance/payables/aging?${query}`);
    return new Response(file.body, { headers: {
      "Content-Type": file.headers.get("content-type") ?? "text/csv; charset=utf-8",
      "Content-Disposition": file.headers.get("content-disposition") ?? 'attachment; filename="payables-aging.csv"',
      "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    } });
  } catch (error) {
    return new Response(error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't download aging.",
      { status: error instanceof ApiError ? error.status : 500 });
  }
}
