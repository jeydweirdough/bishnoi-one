// Changing a platform user's particulars, or moving them to another company.
// Their applications are changed on their own page.
import type { Metadata } from "next";
import { adminsOnly } from "@/src/modules/console/components/gate";
import { UserForm } from "@/src/modules/console/components/users/user-form";
import { enc, load } from "@/src/modules/console/platform/lib/api";
import { PageHeader, Sheet } from "@/src/modules/console/platform/ui/sheet";
import type { Options, PlatformUserDetail } from "@/src/modules/console/lib/types";

type Props = { params: Promise<{ id: string }> };

const getUser = (id: string) => load<{ user: PlatformUserDetail }>(`/platform/users/${enc(id)}`).then((b) => b.user);

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  return { title: `Edit ${(await getUser(id)).fullName}` };
}

export default async function EditUserPage({ params }: Props) {
  const refused = await adminsOnly();
  if (refused) return refused;
  const { id } = await params;
  const [user, options] = await Promise.all([getUser(id), load<Options>("/platform/options")]);
  return (
    <>
      <PageHeader
        title={`Edit ${user.fullName}`}
        crumbs={[
          { href: "/platform/console/users", label: "Users" },
          { href: `/platform/console/users/${user.id}`, label: user.fullName },
        ]}
      />
      <Sheet className="max-w-3xl px-5 py-5 sm:px-6">
        <UserForm companies={options.companies} user={user} />
      </Sheet>
    </>
  );
}
