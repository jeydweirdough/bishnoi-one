import { PhotoPicker } from "@/src/modules/finance/platform/account/photo-picker";
import { Particulars, PageHeader, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { removeMyPhoto, saveMyPhoto } from "@/src/modules/finance/platform/actions/account";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";

export const metadata = { title: "Account" };

/** What this app's /auth/account says about the person signed in. */
type Account = {
  role: { name: string; description: string | null; scope: "own" | "team" | "all" };
  team: { name: string; description: string | null } | null;
  memberSince: string;
  passwordChangedAt: string;
  signedInAt: string;
  previousSignIn: string | null;
  areas: { key: string; name: string; group: string; actions: string[] }[];
};

const REACH = {
  own: "Only the records you own",
  team: "Every record your team owns",
  all: "Every record in this app",
} as const;
const REACH_IN = { own: "the records you own", team: "every record your team owns", all: "every record in this app" } as const;

export default async function AccountPage() {
  const me = await getCompanyMe();
  // An app without /auth/account still shows the picture and the basics.
  const account = await load<Account>("/auth/account").catch(() => null);
  const fmt = makeFormat(me.org);
  const teams = me.modules.flatMap((m) => m.teams.map((t) => `${m.name} · ${t.name}`));
  const team = account?.team?.name ?? (teams.length ? teams.join(", ") : null);
  const groups = Object.entries(Object.groupBy(account?.areas ?? [], (a) => a.group));

  return (
    <>
      <PageHeader title="Account">Your profile photo and access. An administrator sets your name, email, role and team.</PageHeader>

      <div className="grid max-w-[64rem] gap-5 lg:grid-cols-2 lg:items-start">
        <div className="space-y-5">
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="profile">Profile photo</SectionTitle>
            <p className="mb-4 text-meta text-ink-3">
              It appears wherever your name does, for the people you work with. Without one, your initials do.
            </p>
            <PhotoPicker
              name={me.user.fullName}
              id={me.user.id}
              photoAt={me.user.photoAt}
              whose="your"
              onSave={saveMyPhoto}
              onRemove={removeMyPhoto}
            />
          </Sheet>

          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="account">Details</SectionTitle>
            <Particulars
              items={[
                ["Name", me.user.fullName],
                ["Email", me.user.email],
                ["Company", me.org.name],
                [
                  "Role",
                  account ? (
                    <>
                      {account.role.name}
                      {account.role.description && <span className="block text-meta text-ink-3">{account.role.description}</span>}
                    </>
                  ) : (
                    null
                  ),
                ],
                [
                  "Team",
                  team ? (
                    <>
                      {team}
                      {account?.team?.description && <span className="block text-meta text-ink-3">{account.team.description}</span>}
                    </>
                  ) : (
                    null
                  ),
                ],
                ...(account ? ([["Data access", REACH[account.role.scope]]] as [string, string][]) : []),
                ...(account
                  ? ([
                      ["Member since", fmt.whenLabel(account.memberSince)],
                      ["Password last changed", fmt.whenLabel(account.passwordChangedAt)],
                      ["Current sign-in", fmt.whenLabel(account.signedInAt)],
                      ["Previous sign-in", account.previousSignIn ? fmt.whenLabel(account.previousSignIn) : "None"],
                    ] as [string, string][])
                  : []),
              ]}
            />
            <p className="mt-4 text-meta text-ink-3">To correct these details, contact an administrator.</p>
          </Sheet>
        </div>

        {account && (
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="roles">Permissions</SectionTitle>
            <p className="mb-4 text-meta text-ink-3">
              From your role, {account.role.name}, on {REACH_IN[account.role.scope]}
              {account.role.scope === "team" && team ? ` (${team})` : ""}.
            </p>
            {groups.length === 0 ? (
              <p className="text-sm text-ink-3">Your role has no permissions yet. Contact an administrator.</p>
            ) : (
              // One grid for every group, so the actions line up down the page.
              <dl className="grid grid-cols-2 gap-x-5 gap-y-1.5 text-sm">
                {groups.map(([group, areas], i) => (
                  <div key={group} className="contents">
                    <dt className={`text-caps col-span-2 text-ink-3 uppercase ${i ? "mt-3" : ""}`}>{group}</dt>
                    {areas!.map((area) => (
                      <div key={area.key} className="contents">
                        <dt className="text-ink">{area.name}</dt>
                        <dd className="text-ink-2">{area.actions.join(", ")}</dd>
                      </div>
                    ))}
                  </div>
                ))}
              </dl>
            )}
          </Sheet>
        )}
      </div>
    </>
  );
}
