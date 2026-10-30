import { DataCleanupPage } from "@/src/platform/recycle/screen";

export const metadata = { title: "Data clean-up" };

export default function Page() {
  return <DataCleanupPage module="admin" path="/admin/admin/data-cleanup" />;
}
