import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { Flag } from "@/src/modules/pharmacy/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { ApiError, api, enc } from "@/src/modules/pharmacy/platform/lib/api";
import { NoAccess } from "@/src/modules/pharmacy/components/bits";
import { DispenseForm } from "@/src/modules/pharmacy/components/dispense-form";
import { pageFor, param, type Search } from "@/src/modules/pharmacy/lib/page";
import type { Prepared } from "@/src/modules/pharmacy/lib/types";

export const metadata = { title: "New dispensing" };

/** New Dispensing, for one verified prescription from the queue. */
export default async function DispensingNewPage({ searchParams }: { searchParams: Search }) {
  const { me, allowed } = await pageFor("dispensing.create");
  if (!allowed) return <NoAccess what="dispensing" />;
  const rxId = param(await searchParams, "rx");
  // Dispensing always starts from a prescription in the queue.
  if (!rxId) redirect("/pharmacy/dispensing");
  let rx: Prepared;
  try {
    rx = await api.get<Prepared>(`/dispensing/prepare/${enc(rxId)}`);
  } catch (error) {
    // Not verified yet: say so and point back to checking, rather than a bare error.
    if (error instanceof ApiError && error.status === 409) {
      return (
        <>
          <PageHeader crumbs={[{ href: "/pharmacy/dispensing", label: "Dispensing" }]} title="Not ready to dispense" />
          <Sheet>
            <Empty icon="prescriptions" title="This prescription isn't verified">
              {String(error.detail)}{" "}
              <Link href={`/pharmacy/prescriptions/${rxId}`} className="font-semibold text-hema hover:underline">
                Open it to check it
              </Link>
            </Empty>
          </Sheet>
        </>
      );
    }
    if (error instanceof ApiError && error.status === 401) redirect("/login?expired=1");
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  return (
    <>
      <PageHeader crumbs={[{ href: "/pharmacy/dispensing", label: "Dispensing" }]} title={`Dispense ${rx.number}`}>
        For <Link href={`/pharmacy/patients/${rx.patient.id}`} className="font-semibold text-hema hover:underline">{rx.patient.fullName}</Link> · {rx.prescriberName} ·
        verified by {rx.checkedBy?.name ?? "a pharmacist"}
        {rx.patient.allergies && (
          <span className="mt-1 block">
            <Flag letter="!">Allergy: {rx.patient.allergies}</Flag>
          </span>
        )}
      </PageHeader>
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        <DispenseForm rx={rx} org={me.org} />
      </Sheet>
    </>
  );
}
