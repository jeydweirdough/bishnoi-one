import { redirect } from "next/navigation";

export default function SettingsCatchAll() {
  redirect("/admin/admin/users");
}
