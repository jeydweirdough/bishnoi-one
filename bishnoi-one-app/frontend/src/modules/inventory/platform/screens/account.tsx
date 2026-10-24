import { PhotoPicker } from "@/src/modules/inventory/platform/account/photo-picker";
import { Particulars, PageHeader, SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { removeMyPhoto, saveMyPhoto } from "@/src/modules/inventory/platform/actions/account";
import { getCompanyMe } from "@/src/modules/inventory/platform/lib/api";

export const metadata = { title: "Account" };

export default async function AccountPage() {
  const me = await getCompanyMe();
  const teams = me.modules.flatMap((m) => m.teams.map((t) => `${m.name} · ${t.name}`));

  return (
    <>
      <PageHeader title="Account">Your profile photo and access. An administrator manages your name, email and roles.</PageHeader>

      <div className="grid max-w-[52rem] gap-5 lg:grid-cols-2 lg:items-start">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="profile">Profile photo</SectionTitle>
          <p className="mb-4 text-meta text-ink-3">
            Shown next to your name across the app. Your initials appear if no photo is set.
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
              ["Teams", teams.length ? teams.join(", ") : "None"],
            ]}
          />
          <p className="mt-4 text-meta text-ink-3">
            To correct these details, contact an administrator.
          </p>
        </Sheet>
      </div>
    </>
  );
}
