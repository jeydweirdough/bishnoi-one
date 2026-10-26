import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { LogVisitForm } from "@/src/modules/crm/components/field/log-visit";
import type { Doctors } from "@/src/modules/crm/components/field/types";
import { isFieldAgent } from "@/src/modules/crm/components/field/words";
import { lower, termsOf } from "@/src/modules/crm/components/terms/terms";

export const metadata = { title: "Log visit" };

/** Only our own paths, so a crafted link can't send anyone elsewhere after saving. */
function safeBack(value: unknown): string {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//") && !/[\\s]/.test(value) ? value : "/crm/visits";
}

/** A visit, on a page of its own: the fields on the left, the map of one's doctors' clinics on the right. */
export default async function VisitNewPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "visits.create")) return <NoAccess what="logging visits" />;
  const sp = await searchParams;
  const doctors = await load<Doctors>("/field/doctors?limit=500&sort=plan");
  const back = safeBack(sp.back);
  const initial = typeof sp.doctor === "string" && doctors.items.some((d) => d.id === sp.doctor) ? sp.doctor : "";
  const terms = termsOf(me);
  // What the way back is called: the doctor's page, or the list it came from.
  const from = doctors.items.find((d) => d.id === initial)?.name;
  const label = back.startsWith("/crm/customers") && from ? from : back === "/" ? "Home" : back.startsWith("/crm/field/doctors") ? terms.visited.many : back.startsWith("/crm/field/routes") ? "Route" : "Visits";
  return (
    <>
      <PageHeader title="Log visit" crumbs={[{ href: back, label }]}>
        Pick the {lower(terms.visited.one)} on the map or from the list, then record the outcome. Your location is saved with the visit.
      </PageHeader>
      <LogVisitForm
        org={me.org}
        now={new Date().toISOString()}
        doctors={doctors.items.map((d) => ({ id: d.id, name: d.name, pin: d.pin, zone: d.zone }))}
        initial={initial}
        requireLocation={isFieldAgent(me)}
        back={back}
        canAdd={can(me, "customers.create")}
        visitedType={terms.visitedType ?? undefined}
      />
    </>
  );
}
