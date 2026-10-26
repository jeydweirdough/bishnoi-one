import { ClipboardPlus, ExternalLink, Plus, Trash2 } from "lucide-react";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { deletePatient } from "@/src/modules/pharmacy/actions/pharmacy";
import Link from "next/link";
import { LinkButton } from "@/src/modules/pharmacy/platform/ui/button";
import { Flag } from "@/src/modules/pharmacy/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { enc, load } from "@/src/modules/pharmacy/platform/lib/api";
import { Head, NoAccess, SearchBar, Tabs } from "@/src/modules/pharmacy/components/bits";
import { pageFor, param, type Search } from "@/src/modules/pharmacy/lib/page";
import { age } from "@/src/modules/pharmacy/lib/words";
import type { PatientRow } from "@/src/modules/pharmacy/lib/types";

export const metadata = { title: "Patients & customers" };

export default async function PatientsPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed, may } = await pageFor("patients.view");
  if (!allowed) return <NoAccess what="patient records" />;
  const search = await searchParams;
  const kind = param(search, "kind") === "customer" ? "customer" : "patient";
  const q = param(search, "q");
  const rows = await load<PatientRow[]>(`/patients?kind=${kind}${q ? `&q=${enc(q)}` : ""}`);

  return (
    <>
      <PageHeader
        title="Patients & customers"
        actions={
          may("patients.create") && (
            <LinkButton href={`/pharmacy/patients/new?kind=${kind}`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add {kind}
            </LinkButton>
          )
        }
      >
        Patients have prescriptions dispensed to them; customers buy over the counter. Open anyone for their prescription and medication history.
      </PageHeader>
      <Tabs
        label="Patients & customers"
        current={kind}
        tabs={[
          { value: "patient", label: "Patient records", href: "/pharmacy/patients" },
          { value: "customer", label: "Customer records", href: "/pharmacy/patients?kind=customer" },
        ]}
      />
      <div className="mb-3">
        <SearchBar q={q} placeholder="Name, phone or email" keep={kind === "customer" ? { kind } : {}} />
      </div>
      <Sheet>
        {rows.length === 0 ? (
          <Empty icon="patients" title={q ? "Nobody matches" : `No ${kind}s yet`} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <Head columns={["Name", "Born", "Phone", kind === "patient" ? "Prescriptions" : "Allergies", { label: "Last visit", right: true }, { label: "", className: "w-12" }]} />
              <tbody className="divide-y divide-rule">
                {rows.map((p) => {
                  const years = age(p.birthDate);
                  return (
                    <tr key={p.id} className="relative hover:bg-bench/40">
                      <td className="py-3 pr-3 pl-5">
                        <Link href={`/pharmacy/patients/${p.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                          {p.fullName}
                        </Link>
                        {kind === "patient" && p.allergies && (
                          <span className="block">
                            <Flag letter="!">Allergy: {p.allergies}</Flag>
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-ink-2">{p.birthDate ? `${fmt.dateLabel(p.birthDate)}${years !== null ? ` (${years})` : ""}` : "—"}</td>
                      <td className="px-3 py-3 text-ink-2">{p.phone ?? "—"}</td>
                      <td className="px-3 py-3 text-ink-2">{kind === "patient" ? p.prescriptionCount : (p.allergies ?? "—")}</td>
                      <td className="py-3 pr-5 pl-3 text-right text-meta text-ink-2">{p.lastVisitAt ? fmt.whenLabel(p.lastVisitAt) : "—"}</td>
                      <td className="px-2 py-2 text-right">
                        <RowMenu
                          label={`Actions for ${p.fullName}`}
                          items={[
                            { label: "Open", icon: <ExternalLink />, href: `/pharmacy/patients/${p.id}` },
                            ...(kind === "patient" && may("prescriptions.create") ? ["divider" as const, { label: "Receive prescription", icon: <ClipboardPlus />, href: `/pharmacy/prescriptions/new?patient=${p.id}` }] : []),
                            ...(may("patients.delete")
                              ? ["divider" as const, { label: "Delete", icon: <Trash2 />, run: deletePatient.bind(null, p.id), danger: true, confirm: `Delete ${p.fullName}? Only someone with no prescriptions or purchases can be deleted.`, done: `${p.fullName} deleted` }]
                              : []),
                          ]}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Sheet>
    </>
  );
}
