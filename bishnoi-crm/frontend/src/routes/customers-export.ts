import { ApiError, fetchFile } from "@/src/platform/lib/api";

// Customers as a spreadsheet, through here with the signed-in person's token.
// The API decides what's in it (only customers they can reach) and whether
// they may export at all; the list's filters come along in the address.
const PASSED = ["format", "template", "q", "status", "owner"];

export async function GET(request: Request) {
  const from = new URL(request.url).searchParams;
  const query = new URLSearchParams();
  for (const key of PASSED) {
    const value = from.get(key);
    if (value) query.set(key, value);
  }
  try {
    const file = await fetchFile(`/exports/customers${query.size ? `?${query}` : ""}`);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "application/octet-stream",
        "Content-Disposition": file.headers.get("content-disposition") ?? 'attachment; filename="customers.xlsx"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message =
      status === 403 ? "Exporting customers needs the Reports → Export permission. An administrator can give it in Roles." : error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Couldn't make the file.";
    return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }
}
