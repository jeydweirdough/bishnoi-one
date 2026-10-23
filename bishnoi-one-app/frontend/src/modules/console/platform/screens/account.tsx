import { PhotoPicker } from "@/src/modules/console/platform/account/photo-picker";
import { Particulars, PageHeader, SectionTitle, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { removeMyPhoto, saveMyPhoto } from "@/src/modules/console/platform/actions/account";
import { getCompanyMe } from "@/src/modules/console/platform/lib/api";

export const metadata = { title: "My account" };

export default async function AccountPage() {
  const me = await getCompanyMe();
  const teams = me.modules.flatMap((m) => m.teams.map((t) => `${m.name} · ${t.name}`));

  return (
    <>
      <PageHeader title="My account">Your profile picture and access. An admin sets your name, email and roles.</PageHeader>

      <div className="grid max-w-[52rem] gap-5 lg:grid-cols-2 lg:items-start">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="profile">Profile picture</SectionTitle>
          <p className="mb-4 text-meta text-ink-3">
            Shown next to your name throughout the app. Without one, your initials are shown.
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
              ["Teams", teams.length ? teams.join(", ") : "None yet"],
            ]}
          />
          <p className="mt-4 text-meta text-ink-3">
            To correct these details, contact an admin. Admins manage names, emails and access.
          </p>
        </Sheet>
      </div>
    </>
  );
}
