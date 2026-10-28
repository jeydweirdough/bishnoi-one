import { BatchesPage } from "@/src/modules/inventory/screens/stock";
import type { Params, Search } from "@/src/modules/inventory/lib/page";

export const metadata = { title: "Item batches" };
export default async function ItemBatches({ params, searchParams }: { params: Params<{ id: string }>; searchParams: Search }) {
  return <BatchesPage productId={(await params).id} searchParams={searchParams} />;
}
