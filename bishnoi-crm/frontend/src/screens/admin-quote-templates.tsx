import Link from "next/link";
import { FileSpreadsheet, PenLine } from "lucide-react";
import { PageHeader, Sheet, Empty } from "@/src/platform/ui/sheet";
import { can, canAny } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import { DeleteTemplate, NewTemplate } from "../quote-templates/list-actions";
import type { TemplateList } from "../quote-templates/types";

export const metadata = { title: "Quotation templates" };

/** The quotation forms the company prints, one per guarantee-letter issuer
 *  (PCSO, Office of the President, DSWD...) or for any quote. */
export default async function QuoteTemplatesPage() {
  const me = await getCompanyMe();
  if (!canAny(me, ["admin.settings", "department.manage"])) return <NoAccess what="settings" />;
  const list = await load<TemplateList>("/admin/quote-templates");
  // A manager: their own departments' templates, each made for one of them.
  const departmentOnly = !can(me, "admin.settings");
  const newOne = <NewTemplate teams={departmentOnly ? list.teams : undefined} />;
  return (
    <>
      <PageHeader title="Quotation templates" actions={newOne}>
        The quotation forms reps print or download from a quote, with your logo and e-signature. Design one here, or upload the Excel form an issuer
        such as PCSO or the Office of the President asks for.
      </PageHeader>
      <Sheet>
        {list.items.length === 0 ? (
          <Empty title="No quotation templates yet" icon="quotes" actions={newOne}>
            {departmentOnly ? "Until your department has one, its quotes print on the company's." : "Until there is one, quotes print on the standard quotation."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {list.items.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3">
                <span className="text-ink-3">
                  {t.kind === "excel" ? <FileSpreadsheet className="size-5" aria-label="Excel form" /> : <PenLine className="size-5" aria-label="Designed here" />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <Link href={`/admin/settings/quote-templates/${t.id}`} className="font-semibold text-ink hover:text-ink hover:underline">
                      {t.name}
                    </Link>
                    <DeleteTemplate id={t.id} name={t.name} />
                  </div>
                  <p className="text-meta text-ink-3">
                    {[
                      t.payerName ? `For ${t.payerName === "The customer" ? "quotes the customer pays" : `${t.payerName} guarantee letters`}` : "For any quote",
                      t.teamName ? `${t.teamName} team` : null,
                      t.kind === "excel" ? `Excel form${t.excel ? `: ${t.excel.name}` : " (not uploaded yet)"}` : "Designed here",
                      `Next control no. ${t.controlExample}`,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                {!t.isActive && <span className="text-meta text-ink-3">Inactive</span>}
                {(!t.hasLogo || !t.hasSignature) && (
                  <span className="text-meta text-ink-3">{!t.hasLogo && !t.hasSignature ? "No logo or e-signature yet" : !t.hasLogo ? "No logo yet" : "No e-signature yet"}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
