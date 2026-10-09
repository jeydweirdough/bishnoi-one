import { Restricted } from "@/src/components/restricted";
import { getMe, loadQuery } from "@/src/platform/lib/api";
import type { ExecutiveNotification } from "@/src/platform/lib/types";
import { NotificationsScreen } from "@/src/screens/notifications";

export const metadata = { title: "Renewal alerts" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("notifications.view")) return <Restricted what="the renewal alerts" />;
  const notifications = (await loadQuery<{ notifications: ExecutiveNotification[] }>("query Notifications { notifications }", {}, ["notifications"])).notifications;
  return <NotificationsScreen notifications={notifications} can={{ acknowledge: may("notifications.acknowledge"), resolve: may("notifications.resolve") }} />;
}
