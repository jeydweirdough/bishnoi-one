import { redirect } from "next/navigation";

export const metadata = { title: "Add a person" };

/** People are added once for every module, in Bishnoi One's People (R2, decided 2026-10-26). */
export default function NewUserPage() {
  redirect("/platform/roles/people");
}
