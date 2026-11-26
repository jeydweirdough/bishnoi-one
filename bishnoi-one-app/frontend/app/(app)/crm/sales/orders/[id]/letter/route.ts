import { ApiError, enc, fetchFile } from "@/src/platform/lib/api";

// A direct sales order's guarantee letter (2026-11-23), through here with the signed-in person's token: Inventory
// checks they may see the order first. A quote's letter stays with the quote, in the CRM.
export async function GET(_request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const file = await fetchFile(`/inventory/sales-orders/${enc(id)}/letter`);
    return new Response(file.body, {
      headers: {
        "Content-Type": file.headers.get("content-type") ?? "application/octet-stream",
        "Content-Disposition": file.headers.get("content-disposition") ?? "inline",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return new Response(null, { status: error instanceof ApiError ? error.status : 500 });
  }
}
