import { load } from "@/src/platform/lib/api";
import type { ExecutiveNotification } from "@/src/platform/lib/types";
import { NotificationsScreen } from "@/src/screens/notifications";

export const metadata = { title: "Renewal alerts" };

export default async function Page() {
  const notifications = await load<ExecutiveNotification[]>("/admin/notifications");
  return <NotificationsScreen notifications={notifications} />;
}
