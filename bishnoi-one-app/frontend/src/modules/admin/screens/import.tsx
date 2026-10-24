import type { ImportKind } from "@/src/modules/admin/actions/imports";
import { ImportWizard } from "@/src/modules/admin/components/import-wizard";
import { IMPORTS } from "@/src/modules/admin/components/import-words";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";

const TITLES: Record<ImportKind, { title: string; section: string }> = {
  permits: { title: "Import permits", section: "Permits" },
  expatriates: { title: "Import expatriate documents", section: "Expatriates" },
  documents: { title: "Import documents", section: "Documents" },
  properties: { title: "Import properties", section: "Properties" },
};

export function ImportScreen({ kind }: { kind: ImportKind }) {
  const { title, section } = TITLES[kind];
  return (
    <>
      <PageHeader title={title} crumbs={[{ label: section, href: IMPORTS[kind].back }]}>
        Add or update {IMPORTS[kind].many} from an Excel or CSV file.
      </PageHeader>
      <ImportWizard kind={kind} />
    </>
  );
}
