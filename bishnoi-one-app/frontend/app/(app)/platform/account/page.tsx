import { getAccount } from "@/src/platform/lib/account";
import { Avatar } from "@/src/platform/ui/avatar";
import { PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ChangePasswordButton } from "@/src/platform/account/profile-actions";
import { accountSend } from "@/src/platform/lib/account";
import { MySignatureCard } from "@/src/one/account/signature";
import type { PlatformSignature } from "@/src/one/account/signature-actions";

export const metadata = { title: "Your profile" };

export default async function ConsoleProfile() {
  const me = await getAccount();
  const signature = await accountSend<PlatformSignature>("GET", "/identity/signature").catch(() => null);
  const roles = [me.staff === "admin" ? "Platform Administrator" : me.staff === "member" ? "Platform Support" : null, me.isCompanyAdmin ? "Company Administrator" : null].filter(Boolean);
  return <>
    <PageHeader title="Your profile">Your Bishnoi One account, company and access.</PageHeader>
    <Sheet className="mb-5 overflow-hidden">
      <div className="h-24 bg-gradient-to-r from-sage-deep via-sage to-mint sm:h-32" aria-hidden />
      <div className="px-5 pb-5 sm:px-6">
        <div className="-mt-10 flex flex-wrap items-end justify-between gap-3">
          <Avatar name={me.fullName} id={me.id} size="xl" className="ring-4 ring-sheet" />
          <ChangePasswordButton />
        </div>
        <h1 className="mt-3 text-[1.375rem] font-semibold text-ink">{me.fullName}</h1>
        <p className="text-sm text-ink-3">{me.email}</p>
      </div>
    </Sheet>
    <div className="grid gap-5 lg:grid-cols-2">
      <Sheet className="px-5 py-4">
        <SectionTitle icon="profile">Account details</SectionTitle>
        <Particulars items={[
          ["Name", me.fullName],
          ["Email", me.email],
          ["Title", me.title ?? "Not set"],
          ["Company", me.company?.name ?? "Platform"],
          ["Role", roles.join(" / ") || "Member"],
        ]} />
      </Sheet>
      <Sheet className="px-5 py-4">
        <SectionTitle icon="apps">Your applications</SectionTitle>
        {me.apps.length ? <ul className="mt-3 divide-y divide-rule">{me.apps.map(app => <li key={app.key} className="flex flex-wrap justify-between gap-2 py-3 text-sm"><span className="font-medium text-ink">{app.name}</span><span className="text-ink-3">{app.isAppAdmin ? "Administrator" : app.role ?? "Member"}</span></li>)}</ul> : <p className="mt-3 text-sm text-ink-3">No applications assigned to this account.</p>}
      </Sheet>
    </div>
    {signature && <MySignatureCard signature={signature} />}
  </>;
}
