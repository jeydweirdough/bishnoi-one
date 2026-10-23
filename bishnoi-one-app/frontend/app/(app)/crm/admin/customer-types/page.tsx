// Moved under Administration → Settings: the old address goes there.
import { redirect } from "next/navigation";

export default function Page() {
  redirect("/crm/admin/settings/customer-types");
}
