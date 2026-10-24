import { redirect } from "next/navigation";

export const metadata = { title: "Settings Redirect" };

export default function CompanyPage() {
  redirect("/admin/admin/users");
}
