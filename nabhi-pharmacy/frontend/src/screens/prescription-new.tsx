import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/bits";
import { PrescriptionForm } from "../components/prescription-form";
import { pageFor, param, type Search } from "../lib/page";
import type { Medicine, PatientRow, Prescription } from "../lib/types";

export const metadata = { title: "Receive prescription" };

/** Taking a prescription in (or, with an id, correcting one before it's verified). */
export default async function PrescriptionNewPage({ params, searchParams }: { params?: Promise<{ id?: string }>; searchParams: Search }) {
  const id = (await params)?.id;
  const { fmt, allowed, may } = await pageFor(id ? "prescriptions.edit" : "prescriptions.create");
  if (!allowed) return <NoAccess what={id ? "correcting prescriptions" : "receiving prescriptions"} />;
  const search = await searchParams;
  const [patients, medicines, rx] = await Promise.all([
    id ? Promise.resolve([] as PatientRow[]) : load<PatientRow[]>("/patients?limit=500"),
    load<Medicine[]>("/medicines?state=active"),
    id ? load<Prescription>(`/prescriptions/${enc(id)}`) : Promise.resolve(undefined),
  ]);

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/prescriptions", label: "Prescriptions" }, ...(rx ? [{ href: `/prescriptions/${rx.id}`, label: rx.number }] : [])]}
        title={rx ? `Correct ${rx.number}` : "Receive prescription"}
      >
        {rx
          ? `For ${rx.patient.fullName}. Once it's verified it can't be changed, so correct it now.`
          : "It goes into the inbox, where a pharmacist checks and verifies it before anything is dispensed."}
      </PageHeader>
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        {rx && !rx.editable ? (
          <p className="text-ink-2">This prescription is {rx.status === "verified" ? "verified" : "closed"}, so it can't be changed.</p>
        ) : (
          <PrescriptionForm
            rx={rx}
            today={fmt.todayKey()}
            canAddPatients={may("patients.create")}
            presetPatientId={param(search, "patient") || undefined}
            patients={patients.map((p) => ({ id: p.id, fullName: p.fullName, birthDate: p.birthDate, kind: p.kind }))}
            medicines={medicines.map((m) => ({ id: m.id, label: m.label }))}
          />
        )}
      </Sheet>
    </>
  );
}
