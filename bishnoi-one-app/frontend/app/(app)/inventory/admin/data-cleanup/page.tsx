import { DataCleanupPage } from "@/src/platform/recycle/screen";

export const metadata = { title: "Data clean-up" };

export default function Page() {
  return <DataCleanupPage module="inventory" path="/inventory/admin/data-cleanup" />;
}
