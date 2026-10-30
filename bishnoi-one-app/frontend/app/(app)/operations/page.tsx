import { redirect } from "next/navigation";

// Operations opens on its companies.
export default function OperationsHome() {
  redirect("/operations/companies");
}
