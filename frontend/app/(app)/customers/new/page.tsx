// Customers are companies and contacts now: the old address goes to the new section.
import { redirect } from "next/navigation";

export default function Page() {
  redirect("/companies/new");
}
