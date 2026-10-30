// Operators (feature plan step 5): replaces the staff list and staff sessions.
import { load } from "@/src/modules/console/platform/lib/api";
import type { Operator } from "@/src/modules/console/actions/operators";
import { OperatorsList } from "@/src/modules/console/components/access/operators";
import { getAccount } from "@/src/platform/lib/account";
import { PageHeader } from "@/src/platform/ui/sheet";

export const metadata = { title: "Operators" };

export default async function OperatorsPage() {
  const [{ operators }, me] = await Promise.all([load<{ operators: Operator[] }>("/platform/operators"), getAccount()]);
  return (
    <>
      <PageHeader title="Operators">
        The people at Bishnoi One who run it for every company: they see this Operations area and work in any company. Each signs in with an email of their own, never one a company's person uses.
      </PageHeader>
      <div className="max-w-3xl">
        <OperatorsList operators={operators} meEmail={me.email.toLowerCase()} canChange={me.staff === "admin"} />
      </div>
    </>
  );
}
