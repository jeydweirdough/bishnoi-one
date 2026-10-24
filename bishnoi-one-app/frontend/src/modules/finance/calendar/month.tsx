"use client";

import { Check, ChevronLeft, ChevronRight, Pencil, Plus, Trash2, Undo2 } from "lucide-react";
import Link from "next/link";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/modules/finance/platform/ui/button";
import { ConfirmButton } from "@/src/modules/finance/platform/ui/confirm";
import { Field, FormError, Input, Select, Textarea } from "@/src/modules/finance/platform/ui/field";
import { Modal } from "@/src/modules/finance/platform/ui/modal";
import { SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { deleteEvent, saveEvent, setDone } from "@/src/modules/finance/calendar/actions";
import { gridDays } from "@/src/modules/finance/calendar/grid";
import { PAGES, REMINDERS, REPEATS, type CalEvent, type CalItem, type CalendarData, type EventInput, type RemindDays, type Repeat } from "@/src/modules/finance/calendar/types";
import { screen } from "@/src/modules/finance/lib/links";

// The calendar (decided 2026-10-22: Plans/Plan - Finance calendar): a month, Monday
// first, as the CRM's Calendar shows it. Your events and those shared with you;
// Philippine days off and Sundays shaded; liquidations falling due, for whoever
// releases or reviews. Reminders come in the bell and on the Overview.

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const PER_DAY = 4;

function shiftMonth(month: string, by: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + by, 1));
  return d.toISOString().slice(0, 7);
}

const dayLabel = (day: string) => new Date(`${day}T00:00:00Z`).toLocaleDateString("en-PH", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
const monthLabel = (month: string) => new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-PH", { month: "long", year: "numeric", timeZone: "UTC" });

export function CalendarMonth({ data, month, picked }: { data: CalendarData; month: string; picked: { event: string; on: string } | null }) {
  const [selected, setSelected] = useState(picked);
  const [editing, setEditing] = useState<CalEvent | "new" | null>(null);
  const byDay = new Map<string, CalItem[]>();
  for (const i of data.items) byDay.set(i.on, [...(byDay.get(i.on) ?? []), i]);
  const holidays = new Map(data.holidays.map((h) => [h.on, h.name]));
  const dues = new Map<string, CalendarData["liquidations"]>();
  for (const l of data.liquidations) dues.set(l.on, [...(dues.get(l.on) ?? []), l]);
  const current = selected ? data.items.find((i) => i.event.id === selected.event && i.on === selected.on) ?? null : null;
  const thisMonth = data.items.filter((i) => i.on.startsWith(month));

  function chip(i: CalItem) {
    const on = selected?.event === i.event.id && selected.on === i.on;
    return (
      <li key={`${i.event.id}-${i.on}`}>
        <button
          type="button"
          onClick={() => setSelected({ event: i.event.id, on: i.on })}
          title={`${i.event.atTime ? `${i.event.atTime} ` : ""}${i.event.title}${i.event.mine ? "" : ` (shared by ${i.event.owner.name})`}${i.done ? ", done" : ""}`}
          className={`flex w-full items-center gap-1 rounded-md px-1 py-0.5 text-left text-[0.75rem] leading-tight hover:bg-bench ${on ? "bg-hema-tint" : ""} ${
            i.done ? "text-ink-3 line-through decoration-ink-3/50" : "text-ink"
          }`}
        >
          {!i.event.mine && <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-hema" />}
          <span className="truncate">
            {i.event.atTime && <span className="tabular-nums">{i.event.atTime} </span>}
            {i.event.title}
          </span>
        </button>
      </li>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <LinkButton href={`/finance/calendar?month=${shiftMonth(month, -1)}`} size="sm" variant="quiet" aria-label="Previous month" icon={<ChevronLeft className="size-4" aria-hidden />} />
        <h2 className="min-w-40 text-center text-heading">{monthLabel(month)}</h2>
        <LinkButton href={`/finance/calendar?month=${shiftMonth(month, 1)}`} size="sm" variant="quiet" aria-label="Next month" icon={<ChevronRight className="size-4" aria-hidden />} />
        {!data.today.startsWith(month) && (
          <Link href="/finance/calendar" className="text-meta text-hema hover:underline">
            Today
          </Link>
        )}
        <span className="flex-1" />
        <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
          Add an event
        </Button>
      </div>

      <div className="overflow-x-auto">
        <div className="grid min-w-[46rem] grid-cols-7 border-t border-l border-rule">
          {WEEKDAYS.map((d) => (
            <div key={d} className="border-r border-b border-rule bg-bench/60 px-2 py-1.5 text-caps font-semibold text-ink-3 uppercase">
              {d}
            </div>
          ))}
          {gridDays(month).map((day, n) => {
            const inMonth = day.startsWith(month);
            const off = holidays.get(day);
            const shaded = !inMonth || off || n % 7 === 6;
            const list = byDay.get(day) ?? [];
            return (
              <div key={day} className={`min-h-28 border-r border-b border-rule px-1.5 py-1 ${shaded ? "bg-bench/40" : "bg-sheet"}`}>
                <p className={`mb-1 text-meta ${day === data.today ? "inline-flex size-6 items-center justify-center rounded-full bg-hema font-semibold text-white" : inMonth ? "text-ink-2" : "text-ink-3"}`}>
                  {Number(day.slice(8))}
                </p>
                {off && <p className="mb-1 truncate text-[0.6875rem] text-ink-3 italic" title={off}>{off}</p>}
                <ul className="space-y-0.5">{list.slice(0, PER_DAY).map(chip)}</ul>
                {list.length > PER_DAY && (
                  <details className="text-[0.75rem]">
                    <summary className="cursor-pointer px-1 text-ink-3 hover:text-ink">{list.length - PER_DAY} more</summary>
                    <ul className="space-y-0.5">{list.slice(PER_DAY).map(chip)}</ul>
                  </details>
                )}
                {(dues.get(day) ?? []).map((l) => (
                  <Link key={l.id} href={`/finance/funds/${l.id}`} title={`${l.number}: ${l.requester}'s liquidation is due`} className="block truncate rounded-md px-1 py-0.5 text-[0.75rem] leading-tight text-danger hover:bg-bench">
                    Liquidation due: {l.number}
                  </Link>
                ))}
              </div>
            );
          })}
        </div>
      </div>

      {current && <Details item={current} onEdit={() => setEditing(current.event)} onClose={() => setSelected(null)} />}

      <Sheet className="px-5 py-4">
        <SectionTitle icon="calendar">This month</SectionTitle>
        {thisMonth.length === 0 ? (
          <p className="text-sm text-ink-2">Nothing yet. Add your deadlines, cut-offs and monthly tasks, and Finance will remind you.</p>
        ) : (
          <ul className="divide-y divide-rule text-sm">
            {thisMonth.map((i) => (
              <li key={`${i.event.id}-${i.on}`}>
                <button type="button" onClick={() => setSelected({ event: i.event.id, on: i.on })} className="flex w-full items-baseline gap-3 py-1.5 text-left hover:text-hema">
                  <span className="w-24 shrink-0 text-meta text-ink-3">{dayLabel(i.on)}</span>
                  <span className={`min-w-0 flex-1 ${i.done ? "text-ink-3 line-through" : ""}`}>
                    {i.event.atTime && <span className="tabular-nums">{i.event.atTime} </span>}
                    {i.event.title}
                    {!i.event.mine && <span className="text-meta text-ink-3"> · shared by {i.event.owner.name}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Sheet>

      {editing && <EventForm event={editing === "new" ? null : editing} people={data.people} today={data.today} onClose={() => setEditing(null)} />}
    </div>
  );
}

function Details({ item, onEdit, onClose }: { item: CalItem; onEdit: () => void; onClose: () => void }) {
  const [pending, start] = useTransition();
  const e = item.event;
  const remind = REMINDERS.find(([d]) => d === e.remindDays)?.[1] ?? "No reminder";
  const page = PAGES.find(([href]) => href === e.link)?.[1];

  function done(on: boolean) {
    start(async () => {
      const r = await setDone(e.id, item.on, on);
      if (!r.ok) toast.error(r.error);
      else toast.success(on ? `${e.title}: done` : `${e.title}: not done`, { description: on ? "It won't remind anyone for this date." : undefined });
    });
  }

  return (
    <Sheet className="px-5 py-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className={`text-base font-semibold ${item.done ? "text-ink-3 line-through" : ""}`}>{e.title}</h3>
        <span className="text-meta text-ink-2">
          {dayLabel(item.on)}
          {e.atTime ? `, ${e.atTime}` : ""}
        </span>
        <span className="flex-1" />
        <button type="button" onClick={onClose} className="text-meta text-ink-3 hover:text-ink">
          Close
        </button>
      </div>
      <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
        <div>
          <dt className="inline text-ink-3">Repeats: </dt>
          <dd className="inline">{REPEATS[e.repeat]}{e.until ? `, until ${dayLabel(e.until)}` : ""}</dd>
        </div>
        <div>
          <dt className="inline text-ink-3">Reminder: </dt>
          <dd className="inline">{remind}</dd>
        </div>
        <div>
          <dt className="inline text-ink-3">{e.mine ? "Shared with: " : "Added by: "}</dt>
          <dd className="inline">{e.mine ? (e.sharedWith.map((p) => p.name).join(", ") || "nobody (only you)") : e.owner.name}</dd>
        </div>
        {page && e.link && (
          <div>
            <dt className="inline text-ink-3">About: </dt>
            <dd className="inline">
              <Link href={screen(e.link)} className="text-hema hover:underline">
                {page}
              </Link>
            </dd>
          </div>
        )}
      </dl>
      {e.notes && <p className="mt-2 text-sm whitespace-pre-line text-ink-2">{e.notes}</p>}
      {item.done && <p className="mt-2 text-meta text-ink-3">Done by {item.done.by}.</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {item.done ? (
          <Button size="sm" loading={pending} icon={<Undo2 className="size-4" aria-hidden />} onClick={() => done(false)}>
            Not done
          </Button>
        ) : (
          <Button size="sm" variant="primary" loading={pending} icon={<Check className="size-4" aria-hidden />} onClick={() => done(true)}>
            Mark done
          </Button>
        )}
        {e.mine && (
          <>
            <Button size="sm" variant="quiet" icon={<Pencil className="size-4" aria-hidden />} onClick={onEdit}>
              Edit
            </Button>
            <ConfirmButton
              label="Delete"
              icon={<Trash2 className="size-3.5" aria-hidden />}
              triggerVariant="quiet"
              triggerSize="sm"
              title={`Delete “${e.title}”?`}
              body={e.repeat === "none" ? "It's removed from your calendar and from anyone it's shared with." : "Every date it repeats on is removed, from your calendar and from anyone it's shared with."}
              confirmLabel="Delete"
              onConfirm={async () => {
                const r = await deleteEvent(e.id);
                if (!r.ok) {
                  toast.error(r.error);
                  return false;
                }
                toast.success(`${e.title}: deleted`);
                onClose();
              }}
            />
          </>
        )}
      </div>
    </Sheet>
  );
}

function EventForm({ event, people, today, onClose }: { event: CalEvent | null; people: CalendarData["people"]; today: string; onClose: () => void }) {
  const [d, setD] = useState<EventInput>(
    event
      ? { title: event.title, notes: event.notes, startsOn: event.startsOn, atTime: event.atTime, repeat: event.repeat, until: event.until, remindDays: event.remindDays, link: event.link, sharedWith: event.sharedWith.map((p) => p.id) }
      : { title: "", notes: null, startsOn: today, atTime: null, repeat: "none", until: null, remindDays: 1, link: null, sharedWith: [] },
  );
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [pending, start] = useTransition();
  const set = (patch: Partial<EventInput>) => setD({ ...d, ...patch });

  function send() {
    start(async () => {
      const r = await saveEvent(event?.id ?? null, { ...d, title: d.title.trim(), notes: d.notes?.trim() || null });
      if (!r.ok) {
        setError(r.error);
        setFields(r.fields ?? {});
        return;
      }
      toast.success(event ? "Event saved" : "Event added", { description: d.sharedWith.length ? "The people you shared it with are told." : undefined });
      onClose();
    });
  }

  return (
    <Modal open title={event ? "Edit event" : "Add an event"} onCancel={onClose} footer={null} width={560}>
      <form
        noValidate
        className="mt-3 grid gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <div className="sm:col-span-2">
          <Field label="What" error={fields.title} hint="e.g. 2550Q for Q3, ER cut-off, Bank reconciliation">
            {(p) => <Input {...p} value={d.title} maxLength={160} onChange={(e) => set({ title: e.target.value })} autoFocus />}
          </Field>
        </div>
        <Field label="Date" error={fields.startsOn}>
          {(p) => <Input {...p} type="date" value={d.startsOn} onChange={(e) => set({ startsOn: e.target.value })} />}
        </Field>
        <Field label="Time (optional)" error={fields.atTime}>
          {(p) => <Input {...p} type="time" value={d.atTime ?? ""} onChange={(e) => set({ atTime: e.target.value || null })} />}
        </Field>
        <Field label="Repeats" error={fields.repeat}>
          {(p) => (
            <Select {...p} value={d.repeat} onChange={(e) => set({ repeat: e.target.value as Repeat, until: e.target.value === "none" ? null : d.until })}>
              {Object.entries(REPEATS).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {d.repeat !== "none" ? (
          <Field label="Until (optional)" error={fields.until}>
            {(p) => <Input {...p} type="date" value={d.until ?? ""} onChange={(e) => set({ until: e.target.value || null })} />}
          </Field>
        ) : (
          <span className="hidden sm:block" />
        )}
        <Field label="Remind me" error={fields.remindDays} hint="Working days: Monday to Saturday, not counting holidays.">
          {(p) => (
            <Select {...p} value={d.remindDays === null ? "" : String(d.remindDays)} onChange={(e) => set({ remindDays: e.target.value === "" ? null : (Number(e.target.value) as RemindDays) })}>
              {REMINDERS.map(([k, label]) => (
                <option key={label} value={k === null ? "" : String(k)}>
                  {label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="About (optional)" error={fields.link}>
          {(p) => (
            <Select {...p} value={d.link ?? ""} onChange={(e) => set({ link: e.target.value || null })}>
              <option value="">No page</option>
              {PAGES.map(([href, label]) => (
                <option key={href} value={href}>
                  {label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div className="sm:col-span-2">
          <Field label="Notes (optional)" error={fields.notes}>
            {(p) => <Textarea {...p} rows={2} maxLength={1000} value={d.notes ?? ""} onChange={(e) => set({ notes: e.target.value })} />}
          </Field>
        </div>
        <fieldset className="sm:col-span-2">
          <legend className="text-sm font-medium text-ink">Share with</legend>
          {people.length === 0 ? (
            <p className="mt-1 text-meta text-ink-3">Nobody else has the calendar yet. Only you will see it.</p>
          ) : (
            <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1">
              {people.map((p) => (
                <label key={p.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={d.sharedWith.includes(p.id)}
                    onChange={(e) => set({ sharedWith: e.target.checked ? [...d.sharedWith, p.id] : d.sharedWith.filter((x) => x !== p.id) })}
                    className="size-4 accent-[var(--color-hema)]"
                  />
                  {p.name}
                </label>
              ))}
            </div>
          )}
          <p className="mt-1 text-meta text-ink-3">They see it and can mark it done; only you can change it.</p>
          {fields.sharedWith && <p className="text-meta text-danger">{fields.sharedWith}</p>}
        </fieldset>
        <div className="sm:col-span-2">
          <FormError message={error} />
        </div>
        <div className="flex gap-2 sm:col-span-2">
          <Button type="submit" variant="primary" loading={pending}>
            {event ? "Save" : "Add event"}
          </Button>
          <Button variant="quiet" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
        </div>
      </form>
    </Modal>
  );
}
