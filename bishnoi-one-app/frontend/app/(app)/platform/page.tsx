import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { consoleGroups } from "@/src/one/admin-console/frame";

// The Admin Console opens on the first page this person may use.
export default async function AdminConsoleHome() {
  const me = await getAccount();
  const first = consoleGroups(me)[0]?.pages[0]?.href;
  // An operator with no company to run here works in Operations.
  redirect(first ?? (me.staff ? "/operations" : "/?notice=" + encodeURIComponent("The Admin Console is for your company's administrators.")));
}
