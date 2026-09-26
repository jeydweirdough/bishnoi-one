import { load } from "@/src/platform/lib/api";
import type { OfficeTicket } from "@/src/platform/lib/types";
import { TicketsScreen } from "@/src/screens/tickets";

export const metadata = { title: "Office requests" };

export default async function Page() {
  const tickets = await load<OfficeTicket[]>("/admin/tickets");
  return <TicketsScreen tickets={tickets} />;
}
