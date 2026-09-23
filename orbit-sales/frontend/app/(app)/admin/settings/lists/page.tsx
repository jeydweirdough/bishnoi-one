// Pick-lists live in each field now (Settings → Forms): the old address goes there.
import { redirect } from "next/navigation";

export default function Page() {
  redirect("/admin/settings");
}
