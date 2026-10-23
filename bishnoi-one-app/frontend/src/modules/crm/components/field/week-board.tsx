"use client";

import { Check, Plus, Send, Sparkles, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { addStop, fillWeek, removeStop, reviewWeek, sendWeek } from "@/src/modules/crm/actions/field";
import { Button } from "@/src/platform/ui/button";
import { Textarea } from "@/src/platform/ui/field";
import { Combobox } from "@/src/platform/ui/pickers";
import type { DoctorRow, PlanSlot, PlanStop, WeekPlan } from "@/src/modules/crm/components/field/types";
import { ZONES } from "@/src/modules/crm/components/field/words";

// The week's plan, a column a day: the morning for red doctors, midday for
// yellow, the afternoon for green (Rx playbook), 8 calls a day. A visit logged
// to a planned doctor that day ticks it off.

const SLOTS: { value: PlanSlot; label: string }[] = [
  { value: "morning", label: "Morning" },
  { value: "midday", label: "Midday" },
  { value: "afternoon", label: "Afternoon" },
];

export function WeekBoard({ plan, doctors, dayLabel, fullDay }: { plan: WeekPlan; doctors: Pick<DoctorRow, "id" | "name" | "zone" | "tier">[]; dayLabel: Record<string, string>; fullDay: Record<string, string> }) {
  const [pending, start] = useTransition();
  const [note, setNote] = useState(plan.status.note ?? "");
  const run = (work: () => Promise<{ ok: boolean; error?: string }>, done?: string) =>
    start(async () => {
      const r = await work();
      if (!r.ok) toast.error((r as { error: string }).error);
      else if (done) toast.success(done);
    });
  const editable = plan.can.plan;
  const removable = plan.can.plan || plan.can.review;
  const total = plan.days.reduce((n, d) => n + d.stops.length, 0);
  const { status } = plan;

  return (
    <div className="space-y-4">
      {/* Where the week stands with the coach, and what can be done about it. */}
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-rule bg-sheet px-4 py-3">
        <p className="min-w-0 flex-1 text-sm text-ink-2">
          {status.reviewedAt
            ? `Reviewed by ${status.reviewedBy?.name ?? "the coach"}.`
            : status.sentAt
              ? status.changedAt
                ? "Submitted for review; changed since."
                : "Submitted for review: awaiting review."
              : editable
                ? "Plan the week, then submit it for Monday's review."
                : "Not submitted."}
          {status.note && <span className="mt-0.5 block text-meta text-ink-3">“{status.note}”</span>}
        </p>
        {editable && (
          <>
            <Button size="sm" icon={<Sparkles className="size-4" aria-hidden />} loading={pending} onClick={() => run(async () => {
              const r = await fillWeek(plan.week);
              if (r.ok) toast.success(r.data.added ? `${r.data.added} visits added from your zones` : "No visits to add: all zoned doctors are planned.");
              return r;
            })}>
              Auto-fill from zones
            </Button>
            <Button size="sm" variant="primary" icon={<Send className="size-4" aria-hidden />} disabled={!total || (Boolean(status.sentAt) && !status.changedAt && !status.reviewedAt)} onClick={() => run(() => sendWeek(plan.week), "Submitted for review")}>
              {status.sentAt ? "Resubmit for review" : "Submit for review"}
            </Button>
          </>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-5">
        {plan.days.map((d) => {
          const past = d.day < plan.today;
          const count = d.stops.length;
          const onDay = new Set(d.stops.map((s) => s.doctor.id));
          return (
            <section key={d.day} aria-label={fullDay[d.day]} className={`flex min-w-0 flex-col rounded-xl border bg-sheet ${d.day === plan.today ? "border-sage-deep ring-1 ring-sage-deep/30" : "border-rule"}`}>
              <header className="flex items-baseline justify-between gap-2 border-b border-rule px-3 py-2">
                <span className="text-sm font-semibold text-ink">{dayLabel[d.day]}</span>
                <span className={`text-meta tabular-nums ${count >= plan.callsADay ? "font-semibold text-filed" : "text-ink-3"}`}>
                  {count} of {plan.callsADay}
                </span>
              </header>
              <div className="flex-1 space-y-2 px-2 py-2">
                {SLOTS.map((slot) => {
                  const stops = d.stops.filter((s) => s.slot === slot.value);
                  return (
                    <div key={slot.value}>
                      <p className="px-1 text-[0.625rem] font-semibold tracking-wide text-ink-3 uppercase">{slot.label}</p>
                      {stops.length === 0 ? (
                        <p className="px-1 py-1 text-meta text-ink-3/70">—</p>
                      ) : (
                        <ul className="space-y-1">
                          {stops.map((s) => (
                            <Stop key={s.id} stop={s} removable={removable && (!past || plan.can.review)} onRemove={() => run(() => removeStop(s.id), plan.can.review ? "Removed from plan" : undefined)} />
                          ))}
                        </ul>
                      )}
                    </div>
                  );
                })}
              </div>
              {editable && !past && count < 12 && (
                <div className="border-t border-rule p-2">
                  <Combobox
                    size="small"
                    value={null as unknown as string}
                    placeholder={
                      <span className="inline-flex items-center gap-1">
                        <Plus className="size-3.5" aria-hidden />
                        Add a doctor
                      </span>
                    }
                    aria-label={`Add a doctor to ${fullDay[d.day]}`}
                    options={doctors.filter((doc) => !onDay.has(doc.id)).map((doc) => ({ value: doc.id, label: `${doc.name}${doc.zone ? ` · ${ZONES.find((z) => z.value === doc.zone)?.label}` : ""}${doc.tier ? ` · T${doc.tier}` : ""}` }))}
                    onChange={(id) => id && run(() => addStop(id, d.day))}
                    disabled={pending}
                  />
                </div>
              )}
            </section>
          );
        })}
      </div>

      {plan.can.review && status.sentAt && (
        <div className="rounded-xl border border-rule bg-sheet px-4 py-3">
          <p className="mb-2 text-sm font-semibold text-ink">Review</p>
          <p className="mb-2 text-meta text-ink-3">Take off any visit that&apos;s there because the clinic is easy to reach, not because it&apos;s due. Then mark the week reviewed, with a word if you like.</p>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000} placeholder="Review note (optional)" aria-label="Review note" />
          <div className="mt-2 flex justify-end">
            <Button variant="primary" size="sm" icon={<Check className="size-4" aria-hidden />} loading={pending} onClick={() => run(() => reviewWeek(plan.person.id, plan.week, note), "Marked reviewed")}>
              {status.reviewedAt && !status.changedAt ? "Update review" : "Mark reviewed"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function Stop({ stop, removable, onRemove }: { stop: PlanStop; removable: boolean; onRemove: () => void }) {
  const zone = ZONES.find((z) => z.value === stop.doctor.zone);
  return (
    <li className={`group flex items-center gap-1.5 rounded-lg border px-2 py-1.5 text-meta ${stop.visited ? "border-filed/30 bg-mint" : "border-rule bg-bench/60"}`}>
      <span className={`size-2 shrink-0 rounded-full ${zone ? zone.dot : "bg-rule-strong"}`} title={zone ? `${zone.label} zone` : "No zone"} aria-hidden />
      <span className="min-w-0 flex-1">
        <a href={`/crm/companies/${stop.doctor.id}`} className="block truncate font-medium text-ink hover:underline">
          {stop.doctor.name}
        </a>
        <span className="block truncate text-ink-3">
          {stop.doctor.tier ? `T${stop.doctor.tier}` : "No tier"}
          {stop.doctor.city ? ` · ${stop.doctor.city}` : ""}
        </span>
      </span>
      {stop.visited ? (
        <span className="grid size-5 shrink-0 place-items-center rounded-full bg-filed text-white" title="Visited" aria-label="Visited">
          <Check className="size-3" strokeWidth={3} aria-hidden />
        </span>
      ) : (
        removable && (
          <button type="button" onClick={onRemove} className="grid size-5 shrink-0 place-items-center rounded text-ink-3 hover:bg-sheet hover:text-danger" aria-label={`Remove ${stop.doctor.name} from this day`} title="Remove from day">
            <X className="size-3.5" aria-hidden />
          </button>
        )
      )}
    </li>
  );
}
