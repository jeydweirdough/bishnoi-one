import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { consoleGroups } from "@/src/one/admin-console/frame";

// The Admin Console opens on the first page this person may use.
export default async function AdminConsoleHome() {
  const first = consoleGroups(await getAccount())[0]?.pages[0]?.href;
  redirect(first ?? "/?notice=" + encodeURIComponent("The Admin Console is for your company's administrators and Bishnoi One's staff."));
}
