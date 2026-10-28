import { redirect } from "next/navigation";

// The staff list and staff sessions were retired in step 5 (2026-10-28): operators are a switch on
// their Bishnoi One account, kept on Operators; each company's people are on People.
export default function AccountsPage() {
  redirect("/platform/operators");
}
