import { Restricted } from "@/src/components/restricted";
import { getMe, loadQuery } from "@/src/platform/lib/api";
import type { OfficeTicket } from "@/src/platform/lib/types";
import { TicketsScreen } from "@/src/screens/tickets";

export const metadata = { title: "Office requests" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("tickets.view")) return <Restricted what="the office requests" />;
  const tickets = (await loadQuery<{ tickets: OfficeTicket[] }>("query Tickets { tickets }", {}, ["tickets"])).tickets;
  return <TicketsScreen tickets={tickets} can={{ create: may("tickets.create"), edit: may("tickets.edit"), delete: may("tickets.delete") }} />;
}
