import { PhotoPicker } from "../account/photo-picker";
import { Particulars, PageHeader, SectionTitle, Sheet } from "../ui/sheet";
import { removeMyPhoto, saveMyPhoto } from "../actions/account";
import { getCompanyMe } from "../lib/api";

export const metadata = { title: "Your account" };

export default async function AccountPage() {
  const me = await getCompanyMe();
  const teams = me.modules.flatMap((m) => m.teams.map((t) => `${m.name} · ${t.name}`));

  return (
    <>
      <PageHeader title="Your account">Your picture and what you can reach. Your admin sets your name, email and roles.</PageHeader>

      <div className="grid max-w-[52rem] gap-5 lg:grid-cols-2 lg:items-start">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="profile">Picture</SectionTitle>
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
              ["Teams", teams.length ? teams.join(", ") : "None yet"],
            ]}
          />
          <p className="mt-4 text-meta text-ink-3">
            Something wrong here? Ask an admin: they set names, emails and who reaches what.
          </p>
        </Sheet>
      </div>
    </>
  );
}
