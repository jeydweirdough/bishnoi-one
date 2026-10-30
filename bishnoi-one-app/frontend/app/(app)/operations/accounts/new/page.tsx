import { redirect } from "next/navigation";

// Companies → Users and the account pages were retired on 2026-10-29 (one email, one account): each
// company changes its people on People; operators find anyone on Find a person.
export default function RetiredAccountPage() {
  redirect("/operations/people");
}
