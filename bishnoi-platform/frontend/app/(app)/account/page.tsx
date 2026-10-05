// Your own account on the console: who you are here, and your password. The
// shared account screen belongs to a company; platform staff are in none.
import { Particulars, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { getMe } from "@/src/platform/lib/api";
import { getStaff } from "@/src/components/gate";
import { PasswordForm } from "@/src/components/account/password-form";

export const metadata = { title: "Your account" };

export default async function Page() {
  const [me, staff] = await Promise.all([getMe(), getStaff()]);

  return (
    <>
      <PageHeader title="Your account">Your staff account on the platform console.</PageHeader>

      <div className="grid max-w-[52rem] gap-5 lg:grid-cols-2 lg:items-start">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="account">Details</SectionTitle>
          <Particulars
            items={[
              ["Name", me.user.fullName],
              ["Email", me.user.email],
              ["Role", staff.platformRoleName],
            ]}
          />
          <p className="mt-4 text-meta text-ink-3">
            {staff.canAdminister
              ? "A Platform Admin sees and changes everything on the platform. To change your name or email, ask another Platform Admin."
              : "Support sees everything on the platform and works its tickets and incidents. Something wrong here? Ask a Platform Admin."}
          </p>
        </Sheet>

        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="password">Change your password</SectionTitle>
          <PasswordForm />
        </Sheet>
      </div>
    </>
  );
}
