"use client";

import { MapPin, MapPinPlus, Plus } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { logVisit, pinClinic } from "@/src/modules/crm/actions/field";
import { localDateTime } from "@/src/modules/crm/components/crm/words";
import type { CareGroup, VisitOutcome } from "@/src/modules/crm/components/field/types";
import { DetailingFields, type DetailDraft } from "@/src/modules/crm/components/field/detailing-fields";
import { distanceText, locate, metres, NO_LOCATION, type Where } from "@/src/modules/crm/components/field/where";
import { VisitMap, type MapDoctor } from "@/src/modules/crm/components/field/visit-map";
import { AddCustomerDialog } from "@/src/modules/crm/components/crm/new-customer";
import { CARE_GROUP, OUTCOMES } from "@/src/modules/crm/components/field/words";
import { useTerms } from "@/src/modules/crm/components/terms/provider";
import { lower } from "@/src/modules/crm/components/terms/terms";

type Doctor = MapDoctor;

/** A pin is set only from a sure reading (as the API asks): within 100 m. */
const PIN_ACCURACY_M = 100;

/**
 * A visit to a doctor and what came of it, on a page of its own (/visits/new):
 * the fields on the left, the map on the right (on top, on a phone). A
 * collection asks for the amount and the receipt; anything else, just a note.
 * The doctor is picked on the map or from the list, nearest first.
 */
export function LogVisitForm({
  org,
  now,
  doctors = [],
  initial = "",
  requireLocation = false,
  back,
  canAdd = false,
  visitedType,
}: {
  org: Org;
  now: string;
  doctors?: Doctor[];
  /** The doctor picked to start with (from a doctor's own page). */
  initial?: string;
  /** A field agent's visit can't be logged without where they are. */
  requireLocation?: boolean;
  /** Where to go once it's logged, or on Cancel. */
  back: string;
  /** Whether this person can add a doctor (customers.create), and the customer type doctors are. */
  canAdd?: boolean;
  visitedType?: string;
}) {
  const router = useRouter();
  const fmt = useMemo(() => makeFormat(org), [org]);
  const [companyId, setCompanyId] = useState(initial);
  const terms = useTerms();
  // A call: products detailed (Rx playbook). A collection is one pick away.
  const [outcome, setOutcome] = useState<VisitOutcome>("detailed");
  const [careGroup, setCareGroup] = useState<CareGroup>("not_now");
  const [at, setAt] = useState(() => localDateTime(new Date(now), org.timezone));
  const [amount, setAmount] = useState("");
  const [receipt, setReceipt] = useState("");
  const [notes, setNotes] = useState("");
  const [details, setDetails] = useState<DetailDraft[]>([]);
  const [objective, setObjective] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [pending, start] = useTransition();
  const collecting = outcome === "collected";
  // Where you are, asked once as the form opens: the map centres on it, the
  // doctors are listed nearest first, and a clinic can be pinned on the spot.
  const [here, setHere] = useState<Where | null>(null);
  const [placed, setPlaced] = useState<Record<string, Doctor["pin"]>>({});
  const [pinning, startPin] = useTransition();
  const [adding, setAdding] = useState<string | null>(null);
  // Nobody matches what was typed (or the list is empty): say so, and the way forward.
  const notFound = (typed: string) => {
    const one = lower(terms.visited.one);
    return (
      <div className="px-2 py-3 text-center text-meta text-ink-2">
        <p>{typed ? `No ${one} named "${typed}" on your list.` : `No ${lower(terms.visited.many)} on your list yet.`}</p>
        {canAdd ? (
          <Button size="sm" className="mt-2" icon={<Plus className="size-4" aria-hidden />} onMouseDown={(e) => e.preventDefault()} onClick={() => setAdding(typed)}>
            {typed ? `Add ${one} "${typed}"` : `Add ${one}`}
          </Button>
        ) : (
          <p className="mt-1 text-ink-3">Ask your team lead or admin to add them, then log the visit.</p>
        )}
      </div>
    );
  };
  useEffect(() => {
    let gone = false;
    locate().then((r) => !gone && r.ok && setHere(r.where));
    return () => {
      gone = true;
    };
  }, []);
  const all = useMemo(() => doctors.map((d) => (placed[d.id] ? { ...d, pin: placed[d.id] } : d)), [doctors, placed]);
  const away = (d: Doctor) => (here && d.pin ? metres(here, d.pin) : null);
  const listed = useMemo(
    () => (here ? [...all].sort((a, b) => (away(a) ?? Infinity) - (away(b) ?? Infinity)) : all),
    [all, here], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const chosen = all.find((d) => d.id === companyId);
  const canPin = Boolean(chosen && !chosen.pin && here && (here.accuracyM ?? Infinity) <= PIN_ACCURACY_M);

  function pinHere() {
    if (!chosen || !here) return;
    startPin(async () => {
      const r = await pinClinic(chosen.id, here);
      if (!r.ok) return void toast.error(r.error);
      setPlaced((p) => ({ ...p, [chosen.id]: r.data.pin }));
      toast.success("Clinic pinned", { description: `${chosen.name}: visits here now show as at the clinic.` });
    });
  }

  function submit() {
    const cents = collecting ? fmt.toCentavos(amount) : null;
    if (collecting && !cents) {
      setFields({ amountCentavos: "Enter how much was collected." });
      return;
    }
    const used = details.filter((d) => d.productId || d.reaction || d.message.trim());
    const missing: Record<string, string> = {};
    used.forEach((d, i) => {
      if (!d.productId) missing[`detailing.${i}.productId`] = "Pick the product.";
      if (!d.reaction) missing[`detailing.${i}.reaction`] = `Select the ${lower(terms.visited.one)} response.`;
    });
    if (Object.keys(missing).length) {
      setDetails(used);
      setFields(missing);
      return;
    }
    start(async () => {
      // Where the phone is now, if it says: the visit is placed at (or away
      // from) the clinic by it. The browser asks the person the first time.
      const found = await locate();
      if (!found.ok && requireLocation) {
        setError(`${NO_LOCATION[found.why]} Your location is needed to log a visit: turn it on, then log it again.`);
        return;
      }
      const location = found.ok ? found.where : null;
      const result = await logVisit({
        companyId,
        outcome,
        visitedAt: at || null,
        amountCentavos: cents,
        receiptNo: collecting ? receipt.trim() || null : null,
        notes: notes.trim() || null,
        detailing: used.map((d) => ({ productId: d.productId, message: d.message.trim() || null, reaction: d.reaction as Exclude<typeof d.reaction, "">})),
        nextObjective: objective.trim() || null,
        careGroup: outcome === "not_in" ? null : careGroup,
        location,
      });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      const v = result.data;
      toast.success(v.outcome === "collected" ? `Collected ${fmt.peso(v.amountCentavos)}` : "Visit logged", { description: v.company.name });
      router.push(back);
      router.refresh();
    });
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start">
      {/* The map: on the right on a wide screen, kept in view while the form scrolls; on top on a phone. */}
      <aside className="space-y-2 lg:sticky lg:top-4 lg:order-2" aria-label="Map">
        <VisitMap doctors={all} here={here} picked={companyId} onPick={setCompanyId} className="h-72 sm:h-80 lg:h-[calc(100dvh-12rem)]" />
        <p className="text-meta text-ink-3">
          {here ? "Tap a clinic on the map, or pick from the list: nearest first." : "Finding where you are… You can pick from the list meanwhile."}
        </p>
        {chosen && !chosen.pin && (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed border-rule-strong px-3 py-2.5 text-meta text-ink-2">
          <span className="min-w-0 flex-1">
            {chosen.name}&apos;s {lower(terms.site)} isn&apos;t on the map yet.
            {here && !canPin && ` Your phone is only sure of where you are to ${here.accuracyM} m: step outside or wait a moment to pin it.`}
            {!here && " Turn on your location to pin it where you stand."}
          </span>
          {canPin && (
            <Button size="sm" icon={<MapPinPlus className="size-4" aria-hidden />} loading={pinning} onClick={pinHere}>
              Pin current location
            </Button>
          )}
        </div>
        )}
      </aside>
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="min-w-0 space-y-4 rounded-xl border border-rule bg-sheet p-5 shadow-sheet"
    >
      <Field label={terms.visited.one} error={fields.companyId}>
        {(p) => (
          <Select {...p} value={companyId} onChange={(e) => setCompanyId(e.target.value)} required notFound={notFound}>
            <option value="">Select a {lower(terms.visited.one)}</option>
            {listed.map((d) => {
              const m = away(d);
              return (
                <option key={d.id} value={d.id}>
                  {m !== null ? `${d.name} · ${distanceText(m)}` : d.name}
                </option>
              );
            })}
          </Select>
        )}
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Outcome" error={fields.outcome}>
          {(p) => (
            <Select {...p} value={outcome} onChange={(e) => setOutcome(e.target.value as VisitOutcome)}>
              {OUTCOMES.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.value === "not_in" ? `${terms.visited.one} unavailable` : o.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {outcome !== "not_in" && (
          <Field label="Patient Care Group" error={fields.careGroup}>
            {(p) => (
              <Select {...p} value={careGroup} onChange={(e) => setCareGroup(e.target.value as CareGroup)}>
                {CARE_GROUP.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
      </div>
      {collecting && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Amount collected" error={fields.amountCentavos}>
            {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" autoFocus />}
          </Field>
          <Field label="Receipt number" optional hint="The OR or acknowledgment receipt you gave." error={fields.receiptNo}>
            {(p) => <Input {...p} value={receipt} onChange={(e) => setReceipt(e.target.value)} maxLength={40} />}
          </Field>
        </div>
      )}
      <Field label="Date and time" error={fields.visitedAt}>
        {(p) => <Input {...p} type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />}
      </Field>
      {outcome !== "not_in" && (
        <DetailingFields companyId={companyId} rows={details} onRows={setDetails} objective={objective} onObjective={setObjective} errors={fields} />
      )}
      <Field label="Notes" optional error={fields.notes}>
        {(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={collecting ? "Payment notes" : "Visit notes and next steps"} />}
      </Field>
      <FormError message={error} />
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="primary" loading={pending} disabled={!companyId}>
          {collecting ? "Log collection" : "Log visit"}
        </Button>
        <LinkButton href={back} variant="quiet">
          Cancel
        </LinkButton>
        <p className="text-meta text-ink-3">{requireLocation ? "Where you are now is saved with the visit (required)." : "Where you are now is saved with the visit."}</p>
      </div>
    </form>
    {canAdd && (
      <AddCustomerDialog open={adding !== null} onClose={() => setAdding(null)} kind={visitedType} initialName={adding ?? ""} title={`Add ${lower(terms.visited.one)}`} />
    )}
    </div>
  );
}

/** "Log visit": to the visit page (/visits/new), with the doctor picked when there is one, and back here after. */
export function LogVisitButton({
  variant = "default",
  label = "Log visit",
  doctor,
}: {
  variant?: "primary" | "default";
  label?: string;
  org?: Org;
  now?: string;
  doctor?: { id: string; name: string };
  doctors?: Doctor[];
  requireLocation?: boolean;
}) {
  const pathname = usePathname();
  const q = new URLSearchParams({ ...(doctor ? { doctor: doctor.id } : {}), back: pathname });
  return (
    <LinkButton href={`/crm/visits/new?${q}`} variant={variant} icon={<MapPin className="size-4" aria-hidden />}>
      {label}
    </LinkButton>
  );
}
