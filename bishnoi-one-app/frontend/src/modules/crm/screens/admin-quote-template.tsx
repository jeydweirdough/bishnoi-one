import { PageHeader } from "@/src/platform/ui/sheet";
import { can, canAny } from "@/src/modules/crm/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { TemplateEditor } from "@/src/modules/crm/quote-templates/editor";
import type { QuoteTemplate, TemplateList } from "@/src/modules/crm/quote-templates/types";

export const metadata = { title: "Quotation template" };

export default async function QuoteTemplatePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const me = await getCompanyMe();
  if (!canAny(me, ["admin.settings", "department.manage"])) return <NoAccess what="settings" />;
  const [template, list] = await Promise.all([load<QuoteTemplate>(`/admin/quote-templates/${enc(id)}`), load<TemplateList>("/admin/quote-templates")]);
  return (
    <>
      <PageHeader title={template.name} crumbs={[{ href: "/platform/settings/crm/quote-templates", label: "Quotation templates" }]}>
        {template.kind === "excel" ? "An uploaded Excel form, filled in for each quote." : "A quotation designed here, printed from the quote."}
      </PageHeader>
      <TemplateEditor initial={template} options={{ issuers: list.issuers, teams: list.teams, placeholders: list.placeholders, anyTeam: can(me, "admin.settings") }} />
    </>
  );
}
