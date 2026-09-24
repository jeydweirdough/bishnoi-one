import { Pencil, Pill } from "lucide-react";
import Link from "next/link";
import { LinkButton, buttonClass } from "@/src/platform/ui/button";
import { Flag } from "@/src/platform/ui/marks";
import { Particulars, PageHeader, SectionTitle, Sheet, Subheading } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { CheckForm } from "../components/check-form";
import { DispenseMark, NoAccess, Qty, RxClassMark, RxStatusMark } from "../components/bits";
import { pageFor } from "../lib/page";
import { age } from "../lib/words";
import type { Medicine, Prescription } from "../lib/types";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const rx = await load<Prescription>(`/prescriptions/${enc(id)}`);
  return { title: `Check ${rx.number}` };
}

/**
 * Check Prescription: the patient, the prescription as written, the ten
 * checks and the verdict, on one page. Checking is its own step: nothing can
 * be dispensed from here until the prescription is verified, and dispensing
 * happens on its own page.
 */
export default async function PrescriptionPage({ params }: { params: Promise<{ id: string }> }) {
  const { fmt, allowed, may } = await pageFor("prescriptions.view");
  if (!allowed) return <NoAccess what="prescriptions" />;
  const { id } = await params;
  const rx = await load<Prescription>(`/prescriptions/${enc(id)}`);
  const canCheck = may("prescriptions.verify");
  // The catalogue to match against, whenever the check can still change: a
  // verified prescription can be sent back until something is dispensed on it.
  const checkable = canCheck && rx.status !== "rejected" && rx.dispensed === "none";
  const medicines = checkable ? await load<Medicine[]>("/medicines?state=all") : [];
  const patientAge = age(rx.patient.birthDate);
  const owed = rx.items.some((i) => i.remaining > 0);

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/prescriptions", label: "Prescriptions" }]}
        title={
          <span className="inline-flex flex-wrap items-center gap-3">
            <span>Prescription {rx.number}</span>
            <RxStatusMark status={rx.status} />
            {rx.status === "verified" && <DispenseMark state={rx.dispensed} />}
          </span>
        }
        tools={
          rx.editable &&
          may("prescriptions.edit") && (
            <Link href={`/prescriptions/${rx.id}/edit`} title="Correct this prescription's details" aria-label="Correct this prescription's details" className={buttonClass("quiet", "sm", "!px-2")}>
              <Pencil className="size-4" aria-hidden />
            </Link>
          )
        }
        actions={
          rx.status === "verified" &&
          owed &&
          may("dispensing.create") && (
            <LinkButton href={`/dispensing/new?rx=${rx.id}`} variant="primary" icon={<Pill className="size-4" aria-hidden />}>
              Dispense
            </LinkButton>
          )
        }
      >
        Received {fmt.whenLabel(rx.receivedAt).toLowerCase()}
        {rx.receivedBy ? ` by ${rx.receivedBy.name}` : ""}
        {rx.checkedBy && rx.checkedAt ? ` · last checked ${fmt.whenLabel(rx.checkedAt).toLowerCase()} by ${rx.checkedBy.name}${rx.checkedBy.licenseNo ? ` (${rx.checkedBy.licenseNo})` : ""}` : ""}
      </PageHeader>

      {rx.status === "needs_clarification" && rx.verificationNotes && (
        <div role="note" className="mb-4 rounded-[3px] border border-eosin/40 bg-sheet px-4 py-3">
          <Flag letter="?">Needs clarification</Flag>
          <p className="mt-1 text-sm text-ink">{rx.verificationNotes}</p>
        </div>
      )}
      {rx.status === "rejected" && rx.verificationNotes && (
        <div role="note" className="mb-4 rounded-[3px] border border-rule-strong bg-sheet px-4 py-3 text-sm">
          <span className="font-semibold">Rejected:</span> {rx.verificationNotes}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="space-y-4">
          <Sheet className="px-5 py-5">
            <SectionTitle icon="patients">Patient</SectionTitle>
            <div className="mt-3">
              <Particulars
                items={[
                  ["Name", <Link key="n" href={`/patients/${rx.patient.id}`} className="font-semibold text-hema hover:underline">{rx.patient.fullName}</Link>],
                  ["Date of birth", rx.patient.birthDate ? `${fmt.dateLabel(rx.patient.birthDate)}${patientAge !== null ? ` · ${patientAge} years old` : ""}` : null],
                  ["Allergies", rx.patient.allergies ? <Flag key="a" letter="!">{rx.patient.allergies}</Flag> : "None on record"],
                ]}
              />
            </div>
          </Sheet>

          <Sheet className="px-5 py-5">
            <SectionTitle icon="prescriptions">Prescription</SectionTitle>
            <div className="mt-3">
              <Particulars
                items={[
                  ["Prescriber", rx.prescriberName],
                  ["Licence no.", rx.prescriberLicense],
                  ["Clinic", rx.prescriberClinic],
                  ["Prescription date", fmt.dateLabel(rx.prescribedOn)],
                  ...(rx.notes ? ([["Notes", rx.notes]] as [string, string][]) : []),
                ]}
              />
            </div>
            <div className="-mx-5 mt-5 overflow-x-auto border-t border-rule">
              <table className="w-full min-w-[36rem] text-left text-sm">
                <thead>
                  <tr className="text-caps text-ink-3 uppercase">
                    <th scope="col" className="py-3 pr-3 pl-5 font-semibold">Medicine</th>
                    <th scope="col" className="px-3 py-3 text-right font-semibold">Quantity</th>
                    <th scope="col" className="px-3 py-3 font-semibold">Directions</th>
                    <th scope="col" className="py-3 pr-5 pl-3 text-right font-semibold">{rx.status === "verified" ? "Still owed" : "Can give today"}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule border-t border-rule">
                  {rx.items.map((item) => (
                    <tr key={item.id}>
                      <td className="py-3 pr-3 pl-5 align-top">
                        {item.medicine ? (
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold">{item.medicine.label}</span>
                            <RxClassMark rxClass={item.medicine.rxClass} />
                          </span>
                        ) : (
                          <span className="font-semibold text-ink-2">Not matched yet</span>
                        )}
                        <span className="block text-meta text-ink-3">Written as “{item.writtenAs}”</span>
                      </td>
                      <td className="px-3 py-3 text-right align-top">
                        <Qty n={item.quantity} unit={item.medicine?.unit} />
                      </td>
                      <td className="px-3 py-3 align-top text-ink-2">{item.directions ?? "—"}</td>
                      <td className="py-3 pr-5 pl-3 text-right align-top">
                        {rx.status === "verified" ? (
                          <Qty n={item.remaining} />
                        ) : item.available === null ? (
                          <span className="text-ink-3">—</span>
                        ) : item.available < item.quantity ? (
                          <Flag letter="!">{item.available} of {item.quantity}</Flag>
                        ) : (
                          <Qty n={item.available} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Sheet>

          {rx.dispensings.length > 0 && (
            <Sheet className="px-5 py-5">
              <SectionTitle icon="dispensing">Dispensed on it</SectionTitle>
              <ul className="-mx-5 mt-3 divide-y divide-rule border-t border-rule">
                {rx.dispensings.map((d) => (
                  <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-2.5 text-sm">
                    <Link href={`/dispensing/${d.id}`} className="font-semibold text-hema hover:underline">
                      {d.number}
                    </Link>
                    <span className="text-meta text-ink-2">
                      {d.units} units · {fmt.whenLabel(d.dispensedAt)}
                      {d.dispensedBy ? ` · ${d.dispensedBy.name}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </Sheet>
          )}
        </div>

        <Sheet className="h-fit px-5 py-5">
          <SectionTitle icon="approvals">Check</SectionTitle>
          {!canCheck && rx.status !== "verified" && (
            <p className="mt-1 text-meta text-ink-3">A pharmacist checks and verifies it. You can see where it stands.</p>
          )}
          {rx.status === "verified" && rx.dispensed !== "none" && (
            <p className="mt-1 text-meta text-ink-3">Medicines have been dispensed on it, so its verification stands.</p>
          )}
          <div className="mt-4">
            <CheckForm
              key={`${rx.status}-${rx.checkedAt}`}
              rx={rx}
              canCheck={canCheck}
              medicines={medicines.map((m) => ({ id: m.id, label: m.label, status: m.status, rxClass: m.rxClass }))}
            />
          </div>
          {rx.status === "verified" && (
            <div className="mt-5 border-t border-rule pt-4">
              <Subheading>Next</Subheading>
              <p className="mt-1 text-meta text-ink-2">
                {owed ? "It waits in the dispensing queue, where the pharmacist picks the batch for each medicine." : "Everything on it has been dispensed."}
              </p>
            </div>
          )}
        </Sheet>
      </div>
    </>
  );
}
