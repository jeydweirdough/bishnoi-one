"use client";

import { Modal } from "antd";
import { Building2, CircleCheck, CircleX, Clock, Copy, Mail, MapPin, MessageCircle, Phone, Undo2, UserPlus, X } from "lucide-react";
import { lookOf } from "./channel-look";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { addInboxLead, dismissInboxLead, getInboxLead, reopenInboxLead, type InboxDetail, type InboxLead } from "@/src/modules/crm/actions/inbox";
import { Button, IconButton } from "@/src/platform/ui/button";
import { BulkBar, SelectAllBox, SelectBox, SelectableRow, SelectionProvider, useBulkRun, useSelection } from "@/src/platform/bulk/selection";
import { plural } from "@/src/platform/lib/format";
import type { Job } from "@/src/platform/lib/types";
import { Field, Input, Select } from "@/src/platform/ui/field";

// The lead inbox's rows: who, on which channel, what they said last. A new one
// is added to the customers (as a new one, or to the one it turns out to be)
// or dismissed, right beside its name; a dismissed one can be put back.

export type InboxRow = InboxLead & { when: string; handledWhen: string | null };

export function InboxList({ rows }: { rows: InboxRow[] }) {
  const router = useRouter();
  const [open, setOpen] = useState<InboxDetail | null>(null);
  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [busy, startBusy] = useTransition();
  const [loading, setLoading] = useState<string | null>(null);

  async function review(row: InboxRow) {
    setLoading(row.id);
    const r = await getInboxLead(row.id);
    setLoading(null);
    if (!r.ok) return void toast.error(r.error);
    setOpen(r.data);
    setName(r.data.business || r.data.name);
    setType(r.data.types[0]?.code ?? "");
  }

  function add(companyId?: string) {
    if (!open) return;
    startBusy(async () => {
      const r = await addInboxLead(open.id, companyId ? { companyId } : { name, type });
      if (!r.ok) return void toast.error(r.error);
      setOpen(null);
      toast.success(companyId ? `Added to ${r.data.companyName}` : `${r.data.companyName} is now your customer`, {
        description: "The conversation is on the customer, with a task to reply within 4 hours.",
        action: { label: "Open", onClick: () => router.push(`/crm/customers/${r.data.companyId}`) },
      });
    });
  }

  // Dismissing is undone from its own message, so it never asks "are you sure" first.
  function dismiss(row: InboxRow) {
    startBusy(async () => {
      const r = await dismissInboxLead(row.id);
      if (!r.ok) return void toast.error(r.error);
      toast.success(`Dismissed ${row.name}`, { action: { label: "Undo", onClick: () => act(row, reopenInboxLead, `${row.name} is back in New`) } });
    });
  }

  function act(row: InboxRow, run: (id: string) => ReturnType<typeof dismissInboxLead>, done: string) {
    startBusy(async () => {
      const r = await run(row.id);
      if (!r.ok) return void toast.error(r.error);
      toast.success(done);
    });
  }

  // New and dismissed leads can be ticked and dealt with together; added ones are done.
  const pickable = rows.filter((r) => r.status !== "added").map((r) => ({ id: r.id, name: r.name }));
  return (
    <SelectionProvider key={rows.map((r) => r.id).join()} items={pickable}>
      {pickable.length > 1 && (
        <div className="border-b border-rule px-5 sm:px-6">
          <SelectAllBox>
            <span className="text-meta text-ink-3">Select all on this page</span>
          </SelectAllBox>
        </div>
      )}
      {/* Every row the same shape (decided 2026-10-25): the channel as a coloured mark on the left;
          who it is, how to reach them and what they said in the middle; when and what to do on the
          right, always in the same place, so the eye and the pointer go straight to them. */}
      <ul className="divide-y divide-rule">
        {rows.map((row) => {
          const ch = lookOf(row.channel);
          return (
            <SelectableRow key={row.id} id={row.id} as="li" className="grid grid-cols-[auto_2.25rem_minmax(0,1fr)] gap-x-3.5 gap-y-3 px-5 py-4 sm:grid-cols-[auto_2.25rem_minmax(0,1fr)_auto] sm:px-6">
              <span className="flex h-9 w-4 items-center">{row.status !== "added" && <SelectBox id={row.id} label={row.name} />}</span>
              <span className="grid size-9 place-items-center rounded-xl" style={{ background: ch.tint, color: ch.ink }} title={row.channelName}>
                <ch.icon className="size-[1.1rem]" aria-hidden />
                <span className="sr-only">{row.channelName}</span>
              </span>
              <div className="min-w-0">
                <p className="flex min-w-0 items-baseline gap-2">
                  <span className="truncate font-semibold text-ink">{row.name}</span>
                  {row.business && row.business !== row.name && (
                    <span className="flex min-w-0 items-center gap-1 text-sm text-ink-2">
                      <Building2 className="size-3.5 shrink-0 self-center text-ink-3" aria-hidden />
                      <span className="truncate">{row.business}</span>
                    </span>
                  )}
                </p>
                <p className="mt-0.5 flex flex-wrap items-center gap-x-3.5 gap-y-0.5 text-meta text-ink-3">
                  <span className="font-medium" style={{ color: ch.ink }}>{row.channelName}</span>
                  {row.phone && (
                    <span className="inline-flex items-center gap-1">
                      <Phone className="size-3" aria-hidden /> {row.phone}
                    </span>
                  )}
                  {row.email && (
                    <span className="inline-flex min-w-0 items-center gap-1">
                      <Mail className="size-3 shrink-0" aria-hidden /> <span className="truncate">{row.email}</span>
                    </span>
                  )}
                  {row.city && (
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="size-3" aria-hidden /> {row.city}
                    </span>
                  )}
                </p>
                {row.lastMessage && (
                  <p className="mt-2 flex max-w-2xl gap-2 rounded-xl rounded-tl-sm bg-bench px-3 py-2 text-sm text-ink-2">
                    <MessageCircle className="mt-0.5 size-3.5 shrink-0 text-ink-3" aria-hidden />
                    <span className="line-clamp-2">
                      {row.lastMessage}
                      {row.messageCount > 1 && <span className="text-ink-3"> · {row.messageCount} messages</span>}
                    </span>
                  </p>
                )}
                {row.status !== "new" && (
                  <p className="mt-2 flex items-center gap-1.5 text-meta text-ink-3">
                    {row.status === "added" ? <CircleCheck className="size-3.5 text-sage-deep" aria-hidden /> : <CircleX className="size-3.5" aria-hidden />}
                    <span>
                      {row.status === "added" && row.company ? (
                        <>
                          Added to{" "}
                          <Link href={`/crm/customers/${row.company.id}`} className="font-medium text-ink underline-offset-2 hover:underline">
                            {row.company.name}
                          </Link>
                        </>
                      ) : (
                        "Dismissed"
                      )}
                      {row.handledBy && ` by ${row.handledBy}`}
                      {row.handledWhen && `, ${row.handledWhen}`}
                    </span>
                  </p>
                )}
              </div>
              <div className="col-start-3 flex items-center justify-between gap-2 sm:col-start-4 sm:flex-col sm:items-end sm:justify-start">
                <span className="inline-flex items-center gap-1 text-meta whitespace-nowrap text-ink-3">
                  <Clock className="size-3" aria-hidden /> {row.when}
                </span>
                {row.status === "new" && (
                  <span className="inline-flex items-center gap-2">
                    <IconButton label={`Dismiss ${row.name}`} tone="danger" className="max-sm:size-11" disabled={busy} onClick={() => dismiss(row)}>
                      <X className="size-4" aria-hidden />
                    </IconButton>
                    <Button size="sm" icon={<UserPlus className="size-4" aria-hidden />} loading={loading === row.id} onClick={() => review(row)}>
                      Add to customers
                    </Button>
                  </span>
                )}
                {row.status === "dismissed" && (
                  <Button size="sm" variant="quiet" icon={<Undo2 className="size-4" aria-hidden />} disabled={busy} onClick={() => act(row, reopenInboxLead, `${row.name} is back in New`)}>
                    Put back
                  </Button>
                )}
              </div>
            </SelectableRow>
          );
        })}
      </ul>
      <InboxBulk status={rows[0]?.status ?? "new"} />

      <Modal open={open !== null} title={open ? `Add ${open.name} to customers` : ""} onCancel={() => setOpen(null)} footer={null} destroyOnHidden width={620}>
        {open && (
          <div className="space-y-5 pt-1">
            {open.messages.some((m) => m.text) && (
              <section>
                <p className="mb-1.5 text-sm font-medium text-ink">What they said on {open.channelName}</p>
                <ul className="max-h-48 space-y-1.5 overflow-y-auto rounded-xl border border-rule p-3 text-sm text-ink-2">
                  {open.messages
                    .filter((m) => m.text)
                    .map((m, i) => (
                      <li key={i} className="whitespace-pre-line">
                        {m.text}
                      </li>
                    ))}
                </ul>
              </section>
            )}
            {Object.keys(open.details).length > 0 && (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                {Object.entries(open.details).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="text-ink-3">{k}</dt>
                    <dd className="text-ink">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
            {open.matches.length > 0 && (
              <section>
                <p className="mb-1.5 text-sm font-medium text-ink">Already in the CRM?</p>
                <ul className="space-y-2">
                  {open.matches.map((m, i) => (
                    <li key={m.id ?? i} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-rule px-3 py-2">
                      <span className="min-w-0 text-sm">
                        <span className="font-medium text-ink">{m.name}</span>
                        {m.teamName && <span className="text-ink-3"> · {m.teamName}</span>}
                        <span className="block text-meta text-ink-3">{m.why.join(", ")}</span>
                      </span>
                      {m.id ? (
                        <Button size="sm" disabled={busy} onClick={() => add(m.id!)}>
                          It&apos;s them: add to this customer
                        </Button>
                      ) : (
                        <span className="text-meta text-ink-3">Ask that division before adding</span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <section className="space-y-3">
              <p className="text-sm font-medium text-ink">{open.matches.length ? "Or add as a new customer" : "Add as a new customer"}</p>
              <Field label="Customer name">{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={160} />}</Field>
              {open.types.length > 0 && (
                <Field label="Type">
                  {(p) => (
                    <Select {...p} value={type} onChange={(e) => setType(e.target.value)}>
                      {open.types.map((t) => (
                        <option key={t.code} value={t.code}>
                          {t.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              )}
              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="quiet" onClick={() => setOpen(null)}>
                  Cancel
                </Button>
                <Button variant="primary" loading={busy} disabled={!name.trim()} onClick={() => add()}>
                  Add as my customer
                </Button>
              </div>
            </section>
          </div>
        )}
      </Modal>
    </SelectionProvider>
  );
}

/** Each ticked lead, one after another, as one job the bulk bar can report on. */
async function eachOf(ids: string[], run: (id: string) => ReturnType<typeof dismissInboxLead>): Promise<{ ok: true; data: Job }> {
  const failures: Job["failures"] = [];
  for (const id of ids) {
    const r = await run(id);
    if (!r.ok) failures.push({ id, error: r.error });
  }
  return { ok: true, data: { id: "inbox", label: "", status: "done", total: ids.length, processed: ids.length, succeeded: ids.length - failures.length, failed: failures.length, failures } };
}

/** The bar under the inbox once leads are ticked: dismiss them (undone from its message), or put them back. */
function InboxBulk({ status }: { status: InboxRow["status"] }) {
  const s = useSelection();
  const { run, running } = useBulkRun();
  const noun: [string, string] = ["lead", "leads"];
  if (status === "dismissed")
    return (
      <BulkBar noun={noun}>
        <Button size="sm" variant="primary" disabled={running} icon={<Undo2 className="size-4" aria-hidden />}
          onClick={() => run({ doing: "Putting back", did: (n) => `${plural(n, ...noun)} back in New` }, (ids) => eachOf(ids, reopenInboxLead))}>
          Put back
        </Button>
      </BulkBar>
    );
  return (
    <BulkBar noun={noun}>
      <Button size="sm" variant="danger" disabled={running || s.busy.size > 0} icon={<X className="size-4" aria-hidden />}
        onClick={async () => {
          // One message, with Undo, rather than the bar's report and then another.
          const ids = s.ids;
          s.setBusy(ids);
          const { data } = await eachOf(ids, dismissInboxLead);
          s.setBusy([]);
          const gone = ids.filter((id) => !data.failures.some((f) => f.id === id));
          s.keepOnly(data.failures.map((f) => f.id));
          if (gone.length)
            toast.success(`Dismissed ${plural(gone.length, ...noun)}`, {
              description: data.failed ? `${data.failed} couldn't be: ${data.failures[0].error}` : undefined,
              action: { label: "Undo", onClick: () => void eachOf(gone, reopenInboxLead).then(() => toast.success(`${plural(gone.length, ...noun)} back in New`)) },
            });
          else if (data.failed) toast.error(data.failures[0].error);
        }}>
        Dismiss
      </Button>
    </BulkBar>
  );
}

/** A channel's address, to give to Meta, Viber, Tawk.to or the website, with a copy button. */
export function CopyAddress({ address }: { address: string }) {
  return (
    <span className="flex min-w-0 items-center gap-1.5">
      <code className="min-w-0 truncate rounded bg-bench px-1.5 py-0.5 text-meta text-ink-2">{address}</code>
      <Button
        size="sm"
        variant="quiet"
        aria-label="Copy address"
        icon={<Copy className="size-3.5" aria-hidden />}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(address);
            toast.success("Address copied");
          } catch {
            toast.error("Couldn't copy: select it and copy it by hand.");
          }
        }}
      />
    </span>
  );
}

/** Which channel the list shows: one dropdown in the list's tool row, rather than seven chips. */
export function ChannelFilter({ value, options }: { value: string; options: readonly { value: string; label: string }[] }) {
  const router = useRouter();
  const [, start] = useTransition();
  return (
    <label className="flex items-center gap-2 text-meta text-ink-3">
      Channel
      <select
        suppressHydrationWarning
        value={value}
        onChange={(e) => {
          const next = new URLSearchParams(window.location.search);
          if (e.target.value) next.set("channel", e.target.value);
          else next.delete("channel");
          next.delete("page");
          start(() => router.replace(`/crm/inbox${next.size ? `?${next}` : ""}`, { scroll: false }));
        }}
        className="h-9 rounded-lg border border-rule bg-white px-2.5 text-sm text-ink outline-none focus:border-ink"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
