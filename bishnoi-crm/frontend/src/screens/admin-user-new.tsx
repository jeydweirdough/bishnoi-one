import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { USERS, can, canAny } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { UserOptions } from "@/src/platform/lib/types";
import { UserForm } from "../components/admin/user-form";
import { NoAccess } from "../components/admin/words";

export const metadata = { title: "Add a person" };

export default async function NewUserPage() {
  const me = await getCompanyMe();
  if (!canAny(me, USERS)) return <NoAccess what="managing users" />;
  const options = await load<UserOptions>("/admin/users/options");

  return (
    <>
      <PageHeader title="Add a person" crumbs={[{ href: "/admin/users", label: "Users" }]}>
        They sign in to Sales with this email and the first password you give them.
      </PageHeader>
      <Sheet className="px-5 pt-5 pb-6">
        <UserForm {...options} />
      </Sheet>
    </>
  );
}
