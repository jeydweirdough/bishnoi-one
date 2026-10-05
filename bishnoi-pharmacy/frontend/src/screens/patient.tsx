import { ClipboardPlus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Flag } from "@/src/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { Head, NoAccess, RxClassMark, RxStatusMark, Tabs } from "../components/bits";
import { DeleteRecord } from "../components/delete-record";
import { PatientForm } from "../components/patient-form";
import { pageFor, param, type Search } from "../lib/page";
import { age } from "../lib/words";
import type { PatientDetail } from "../lib/types";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return { title: (await load<PatientDetail>(`/patients/${enc(id)}`)).fullName };
}

/** One person: their record, every prescription they've brought, and everything they've been given. */
export default async function PatientPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Search }) {
  const { fmt, allowed, may } = await pageFor("patients.view");
  if (!allowed) return <NoAccess what="patient records" />;
  const { id } = await params;
  const tab = ["prescriptions", "medications"].includes(param(await searchParams, "tab")) ? param(await searchParams, "tab") : "details";
  const p = await load<PatientDetail>(`/patients/${enc(id)}`);
  const years = age(p.birthDate);
  const base = `/patients/${p.id}`;

  return (
    <>
      <PageHeader
        crumbs={[{ href: p.kind === "customer" ? "/patients?kind=customer" : "/patients", label: p.kind === "customer" ? "Customer records" : "Patient records" }]}
        title={p.fullName}
        tools={
          may("patients.delete") && (
            <DeleteRecord
              what={p.kind}
              name={p.fullName}
              kind="patient"
              id={p.id}
              after="/patients"
              body="Only someone with no prescriptions or purchases can be deleted: those records must be kept."
            />
          )
        }
        actions={
          may("prescriptions.create") && (
            <LinkButton href={`/prescriptions/new?patient=${p.id}`} icon={<ClipboardPlus className="size-4" aria-hidden />}>
              Receive a prescription
            </LinkButton>
          )
        }
      >
        {p.kind === "customer" ? "Customer" : "Patient"}
        {p.birthDate ? ` · born ${fmt.dateLabel(p.birthDate)}${years !== null ? ` (${years})` : ""}` : ""}
        {p.phone ? ` · ${p.phone}` : ""}
        {p.allergies && (
          <span className="mt-1 block">
            <Flag letter="!">Allergy: {p.allergies}</Flag>
          </span>
        )}
      </PageHeader>
      <Tabs
        label={p.fullName}
        current={tab}
        tabs={[
          { value: "details", label: "Details", href: base },
          { value: "prescriptions", label: "Prescription history", href: `${base}?tab=prescriptions`, count: p.prescriptions.length },
          { value: "medications", label: "Medication history", href: `${base}?tab=medications`, count: p.medications.length },
        ]}
      />

      {tab === "details" && (
        <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
          <PatientForm key={p.updatedAt} patient={p} today={fmt.todayKey()} canEdit={may("patients.edit")} />
        </Sheet>
      )}

      {tab === "prescriptions" && (
        <Sheet>
          {p.prescriptions.length === 0 ? (
            <Empty icon="prescriptions" title="No prescriptions yet" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <Head columns={["Prescription", "Medicines", "Status", { label: "Received", right: true }]} />
                <tbody className="divide-y divide-rule">
                  {p.prescriptions.map((rx) => (
                    <tr key={rx.id} className="relative hover:bg-bench/40">
                      <td className="py-3 pr-3 pl-5 align-top">
                        <Link href={`/prescriptions/${rx.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                          {rx.number}
                        </Link>
                        <span className="block text-meta text-ink-3">
                          {rx.prescriberName} · {fmt.dateLabel(rx.prescribedOn)}
                        </span>
                      </td>
                      <td className="px-3 py-3 align-top text-ink-2">
                        {rx.items.map((i) => (
                          <span key={i.writtenAs} className="block">
                            {i.writtenAs} · {i.qtyDispensed} of {i.quantity} given
                          </span>
                        ))}
                      </td>
                      <td className="px-3 py-3 align-top">
                        <RxStatusMark status={rx.status} />
                      </td>
                      <td className="py-3 pr-5 pl-3 text-right align-top text-meta text-ink-2">{fmt.whenLabel(rx.receivedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Sheet>
      )}

      {tab === "medications" && (
        <Sheet>
          {p.medications.length === 0 ? (
            <Empty icon="medicines" title="Nothing given yet" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[44rem] text-left text-sm">
                <Head columns={["Medicine", { label: "Quantity", right: true }, "Batch", "Through", { label: "When", right: true }]} />
                <tbody className="divide-y divide-rule">
                  {p.medications.map((m, n) => (
                    <tr key={n}>
                      <td className="py-3 pr-3 pl-5">
                        <span className="flex flex-wrap items-center gap-2">
                          <Link href={`/medicines/${m.medicineId}`} className="font-semibold text-hema hover:underline">
                            {m.medicine}
                          </Link>
                          <RxClassMark rxClass={m.rxClass} />
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">
                        {m.quantity} <span className="text-meta text-ink-3">{m.unit}</span>
                      </td>
                      <td className="px-3 py-3 text-ink-2">Lot {m.lotNo}</td>
                      <td className="px-3 py-3">
                        <Link href={`/sales/${m.saleId}`} className="text-hema hover:underline">
                          {m.dispensingNumber ?? m.saleNumber}
                        </Link>
                      </td>
                      <td className="py-3 pr-5 pl-3 text-right text-meta text-ink-2">{fmt.whenLabel(m.at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Sheet>
      )}
    </>
  );
}
