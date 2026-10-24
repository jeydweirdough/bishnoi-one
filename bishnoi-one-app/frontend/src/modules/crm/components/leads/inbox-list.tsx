"use client";

import { Modal } from "antd";
import { Check, Copy, Mail, MessageCircle, Phone, Undo2, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { addInboxLead, dismissInboxLead, getInboxLead, reopenInboxLead, type InboxDetail, type InboxLead } from "@/src/modules/crm/actions/inbox";
import { Button } from "@/src/platform/ui/button";
import { Field, Input, Select } from "@/src/platform/ui/field";
import { Pill } from "@/src/platform/ui/figures";

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
        action: { label: "Open", onClick: () => router.push(`/crm/companies/${r.data.companyId}`) },
      });
    });
  }

  function act(row: InboxRow, run: (id: string) => ReturnType<typeof dismissInboxLead>, done: string) {
    startBusy(async () => {
      const r = await run(row.id);
      if (!r.ok) return void toast.error(r.error);
      toast.success(done);
    });
  }

  return (
    <>
      <ul className="divide-y divide-rule">
        {rows.map((row) => (
          <li key={row.id} className="grid gap-x-4 gap-y-2 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:px-6">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
                <span className="font-semibold text-ink">{row.name}</span>
                {row.business && row.business !== row.name && <span className="text-ink-2">{row.business}</span>}
                <Pill tone="plain" dot={false}>
                  {row.channelName}
                </Pill>
                {row.status === "new" && (
                  <span className="inline-flex gap-1">
                    <Button size="sm" variant="primary" icon={<Check className="size-4" aria-hidden />} loading={loading === row.id} onClick={() => review(row)}>
                      Add to customers
                    </Button>
                    <Button size="sm" variant="quiet" icon={<X className="size-4" aria-hidden />} disabled={busy} onClick={() => act(row, dismissInboxLead, `Dismissed ${row.name}`)}>
                      Dismiss
                    </Button>
                  </span>
                )}
                {row.status === "dismissed" && (
                  <Button size="sm" variant="quiet" icon={<Undo2 className="size-4" aria-hidden />} disabled={busy} onClick={() => act(row, reopenInboxLead, `${row.name} is back in New`)}>
                    Put back
                  </Button>
                )}
              </div>
              {(row.phone || row.email || row.city) && (
                <p className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-meta text-ink-3">
                  {row.phone && (
                    <span className="inline-flex items-center gap-1">
                      <Phone className="size-3.5" aria-hidden /> {row.phone}
                    </span>
                  )}
                  {row.email && (
                    <span className="inline-flex items-center gap-1">
                      <Mail className="size-3.5" aria-hidden /> {row.email}
                    </span>
                  )}
                  {row.city && <span>{row.city}</span>}
                </p>
              )}
              {row.lastMessage && (
                <p className="mt-1.5 flex gap-1.5 text-sm text-ink-2">
                  <MessageCircle className="mt-0.5 size-3.5 shrink-0 text-ink-3" aria-hidden />
                  <span className="line-clamp-2">
                    {row.lastMessage}
                    {row.messageCount > 1 && <span className="text-ink-3"> · {row.messageCount} messages</span>}
                  </span>
                </p>
              )}
              {row.status !== "new" && (
                <p className="mt-1.5 text-meta text-ink-3">
                  {row.status === "added" && row.company ? (
                    <>
                      Added to{" "}
                      <Link href={`/crm/companies/${row.company.id}`} className="font-medium text-ink underline-offset-2 hover:underline">
                        {row.company.name}
                      </Link>
                    </>
                  ) : (
                    "Dismissed"
                  )}
                  {row.handledBy && ` by ${row.handledBy}`}
                  {row.handledWhen && `, ${row.handledWhen}`}
                </p>
              )}
            </div>
            <span className="text-meta whitespace-nowrap text-ink-3 sm:text-right">{row.when}</span>
          </li>
        ))}
      </ul>

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
    </>
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
