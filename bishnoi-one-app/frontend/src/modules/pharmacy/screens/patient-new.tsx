import { PageHeader, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { NoAccess } from "@/src/modules/pharmacy/components/bits";
import { PatientForm } from "@/src/modules/pharmacy/components/patient-form";
import { pageFor, param, type Search } from "@/src/modules/pharmacy/lib/page";

export const metadata = { title: "Add patient or customer" };

export default async function PatientNewPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed } = await pageFor("patients.create");
  if (!allowed) return <NoAccess what="adding patients" />;
  const kind = param(await searchParams, "kind") === "customer" ? "customer" : "patient";
  return (
    <>
      <PageHeader crumbs={[{ href: "/pharmacy/patients", label: "Patients & customers" }]} title={`Add ${kind}`} />
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        <PatientForm kind={kind} today={fmt.todayKey()} />
      </Sheet>
    </>
  );
}
