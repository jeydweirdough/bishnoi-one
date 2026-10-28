import { redirect } from "next/navigation";
import type { Search } from "@/src/modules/inventory/lib/page";

// Preserve saved links while keeping batch work in the item context.
export default async function LegacyBatches({ searchParams }: { searchParams: Search }) {
  const search = await searchParams;
  const product = typeof search.product === "string" ? search.product : "";
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(search)) {
    if (key !== "product" && typeof value === "string") query.set(key, value);
  }
  const base = product ? `/inventory/products/${encodeURIComponent(product)}/batches` : "/inventory/reports/batch-expiry";
  redirect(`${base}${query.size ? `?${query}` : ""}`);
}
