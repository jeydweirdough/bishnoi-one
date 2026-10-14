// Your own account on the console: who you are here, and your password. The
// shared account screen belongs to a company; platform staff are in none.
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { getMe } from "@/src/platform/lib/api";
import { getStaff } from "@/src/components/gate";
import { DetailsForm } from "@/src/components/account/details-form";
import { PasswordForm } from "@/src/components/account/password-form";

export const metadata = { title: "My account" };

export default async function Page() {
  const [me, staff] = await Promise.all([getMe(), getStaff()]);

  return (
    <>
      <PageHeader title="My account">Your staff account on the platform console.</PageHeader>

      <div className="grid max-w-[52rem] gap-5 lg:grid-cols-2 lg:items-start">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="account">Details</SectionTitle>
          <DetailsForm id={me.user.id} no={me.user.no ?? null} fullName={me.user.fullName} email={me.user.email} role={staff.platformRoleName} />
          <p className="mt-4 text-meta text-ink-3">
            {staff.canAdminister
              ? "A Platform Admin sees and changes everything on the platform. Your role is changed by another Platform Admin."
              : "Support sees everything on the platform and works its tickets and incidents. Your role is changed by a Platform Admin."}
          </p>
        </Sheet>

        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="password">Change password</SectionTitle>
          <PasswordForm />
        </Sheet>
      </div>
    </>
  );
}
