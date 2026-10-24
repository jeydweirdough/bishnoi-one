"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { CalendarCheck, CircleCheck, FileText, Info, Pencil, StickyNote, Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { deleteOperation, logStep, type OperationsPath } from "@/src/modules/admin/actions/operations";
import { KINDS, day, type Item } from "@/src/modules/admin/components/operations/kinds";
import { RecordForm } from "@/src/modules/admin/components/operations/record-form";
import { Initials, Tag } from "@/src/modules/admin/components/record-table";
import { Button } from "@/src/modules/admin/platform/ui/button";
import { ConfirmButton } from "@/src/modules/admin/platform/ui/confirm";

type Event = { id: string; kind: string; text: string; by: string | null; at: string };
type Can = { edit: boolean; delete: boolean };

const EVENT_ICON: Record<string, typeof Info> = { added: Info, changed: Pencil, note: StickyNote };

/**
 * One record, as the CRM's customer page: the card with its name, tag, facts
 * and quick steps; its history; its details beside.
 */
export function OperationRecord({ path, data, can }: { path: OperationsPath; data: { record: Item; history: Event[]; steps: string[] }; can: Can }) {
  const kind = KINDS[path];
  const router = useRouter();
  const [record, setRecord] = useState<Item>(data.record);
  const [history, setHistory] = useState<Event[]>(data.history);
  const [editing, setEditing] = useState(false);
  const [noting, setNoting] = useState(false);
  const [note, setNote] = useState("");
  const [pending, start] = useTransition();
  const name = kind.name(record);
  const status = kind.status(record);
  const steps = kind.steps.filter((s) => data.steps.includes(s.action));
  const main = steps.find((s) => s.primary?.(record));

  function step(action: string, words?: string) {
    start(async () => {
      const r = await logStep(path, record.id, action, words);
      if (!r.ok) return void toast.error(r.error);
      setRecord(r.data.record as Item);
      setHistory(r.data.history as Event[]);
      setNote("");
      setNoting(false);
      toast.success(action === "note" ? "Note added" : (kind.steps.find((s) => s.action === action)?.label ?? "Done"), { description: name });
    });
  }

  return (
    <>
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-[13px] text-ink-3">
        <Link href={kind.route} className="hover:text-ink hover:underline">
          {kind.title}
        </Link>
        <span aria-hidden>›</span>
        <span className="truncate">{name}</span>
      </nav>

      <section className="mt-3 rounded-[22px] border-[1.5px] border-ink bg-sheet px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-start gap-4">
          <span className="scale-125 origin-top-left pt-0.5 sm:mr-2">
            <Initials name={name} filled glyph={kind.glyph?.(record)} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-[1.75rem] leading-tight font-semibold tracking-[-0.02em] text-ink">{name}</h1>
              {path === "vehicles" && typeof record.plate === "string" && record.plate && (
                <span className="rounded-[6px] border-[1.5px] border-ink px-2 py-px text-[12.5px] font-semibold tracking-[0.05em]">{record.plate}</span>
              )}
              {can.edit && (
                <button type="button" onClick={() => setEditing(true)} aria-label={`Change ${name}`} title="Change details" className="grid size-9 place-items-center rounded-full text-ink-3 hover:bg-mint hover:text-ink">
                  <Pencil className="size-4" aria-hidden />
                </button>
              )}
            </div>
            {kind.subline(record) && <p className="mt-0.5 text-[13.5px] text-ink-3">{kind.subline(record)}</p>}
            {status && (
              <div className="mt-2.5">
                <Tag tone={status.tone} dot>
                  {status.text}
                </Tag>
              </div>
            )}
          </div>
          {can.edit && main && (
            <Button variant="primary" disabled={pending} onClick={() => step(main.action)}>
              {main.label}
            </Button>
          )}
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-rule pt-4 sm:grid-cols-4">
          {kind.facts(record).map((f) => (
            <div key={f.label} className="min-w-0">
              <dt className="text-[12px] text-ink-3">{f.label}</dt>
              <dd className="truncate text-[13.5px] font-medium text-ink">{f.value}</dd>
            </div>
          ))}
        </dl>

        {can.edit && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-rule pt-4">
            <span className="mr-1 text-[13px] text-ink-3">Log</span>
            {steps.map((s) => (
              <Button key={s.action} size="sm" disabled={pending} onClick={() => step(s.action)}>
                {s.label}
              </Button>
            ))}
            <Button size="sm" disabled={pending} onClick={() => setNoting((n) => !n)} aria-expanded={noting}>
              Note
            </Button>
          </div>
        )}
        {noting && (
          <form
            className="mt-3 flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (note.trim()) step("note", note.trim());
            }}
          >
            <label className="min-w-64 flex-1">
              <span className="sr-only">Note</span>
              <input
                autoFocus
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={500}
                placeholder="What happened, e.g. brake pads replaced"
                className="h-10 w-full rounded-full border border-control bg-sheet px-4 text-sm focus:border-ink focus:ring-3 focus:ring-mint-2 focus:outline-none"
              />
            </label>
            <Button type="submit" variant="primary" size="sm" disabled={pending || !note.trim()}>
              Add note
            </Button>
          </form>
        )}
      </section>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-start">
        <section className="rounded-[22px] border border-rule bg-sheet px-5 pt-3 pb-5">
          <div className="flex gap-1.5 border-b border-rule">
            <span className="relative px-3.5 pt-2.5 pb-3 text-sm font-medium text-ink">
              History <span className="ml-1 text-[11.5px] text-ink-3">{history.length}</span>
              <span className="absolute inset-x-2.5 -bottom-px h-[3px] rounded-t-[3px] bg-ink" aria-hidden />
            </span>
          </div>
          <ol className="mt-4">
            {history.map((e, n) => {
              const I = EVENT_ICON[e.kind] ?? (e.kind.includes("renewed") ? CalendarCheck : e.kind === "pms_done" || e.kind === "booked" || e.kind === "approved" ? CircleCheck : FileText);
              return (
                <li key={e.id} className="relative grid grid-cols-[38px_minmax(0,1fr)_auto] gap-3.5 pb-[18px]">
                  {n < history.length - 1 && <span className="absolute top-10 bottom-0.5 left-[18px] w-[1.5px] bg-rule" aria-hidden />}
                  <span className="grid size-[38px] place-items-center rounded-full border-[1.5px] border-ink bg-sheet">
                    <I className="size-[18px]" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <p className="font-semibold text-ink">{e.text}</p>
                    <p className="text-[12.5px] text-ink-3">{e.by ?? "Bishnoi One"}</p>
                  </div>
                  <time dateTime={e.at} className="text-[12.5px] whitespace-nowrap text-ink-3">
                    {day(e.at.slice(0, 10))}
                  </time>
                </li>
              );
            })}
          </ol>
        </section>

        <section className="rounded-[22px] border border-rule bg-sheet px-5 py-5">
          <h2 className="text-[17px] font-semibold text-ink">Details</h2>
          {kind.details(record).map((section) => {
            const filled = section.rows.filter((r) => r.value).length;
            return (
              <div key={section.title} className="mt-4 border-t border-rule pt-3.5">
                <p className="flex items-center justify-between text-sm font-semibold text-ink">
                  {section.title}
                  <span className="text-[12.5px] font-normal text-ink-3">
                    {filled} of {section.rows.length}
                  </span>
                </p>
                <dl className="mt-3 space-y-3">
                  {section.rows.map((r) => (
                    <div key={r.label}>
                      <dt className="text-[12px] text-ink-3">{r.label}</dt>
                      <dd className={`text-[13.5px] whitespace-pre-line ${r.value ? "font-medium text-ink" : "text-ink-3"}`}>
                        {r.value ?? (can.edit ? (
                          <button type="button" onClick={() => setEditing(true)} className="underline hover:text-ink">
                            Add
                          </button>
                        ) : (
                          "Not set"
                        ))}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            );
          })}
          {can.delete && (
            <div className="mt-5 border-t border-rule pt-4">
              <ConfirmButton
                label={`Delete this ${kind.one}`}
                icon={<Trash2 className="size-4" aria-hidden />}
                triggerVariant="quiet"
                triggerSize="sm"
                triggerClassName="!text-danger hover:!bg-danger/10"
                title={`Delete ${name}?`}
                body={`This ${kind.one}, its history and its alerts are deleted. This can't be undone.`}
                confirmLabel={`Delete ${kind.one}`}
                danger
                onConfirm={async () => {
                  const r = await deleteOperation(path, record.id);
                  if (!r.ok) {
                    toast.error(r.error);
                    return false;
                  }
                  toast.success("Deleted", { description: name });
                  router.push(kind.route);
                }}
              />
            </div>
          )}
        </section>
      </div>

      {editing && (
        <RecordForm
          kind={kind}
          item={record}
          onClose={() => setEditing(false)}
          onSaved={(saved) => {
            setRecord(saved);
            router.refresh();
          }}
        />
      )}
    </>
  );
}
