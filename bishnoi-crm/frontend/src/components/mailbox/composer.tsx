"use client";

import { Input, Modal, Select } from "antd";
import Link from "next/link";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";
import { FormError } from "@/src/platform/ui/field";
import { findCustomers } from "../../actions/deals";
import { customerAddresses, listTemplates, readMailbox, sendEmail, type EmailTemplate, type MailboxInfo } from "../../actions/mailbox";

type Option = { value: string; label: string };
export type ComposeFor = { id: string; name: string };

/**
 * Writing an email in the CRM. It goes out through the provider of the mailbox
 * picked in From (Zoho Mail, Gmail, Outlook, or any by SMTP), and is kept on
 * the customer. An approved email is sent as approved, with a personal note on
 * top; or the person writes their own.
 */
export function Composer({ open, onClose, customer }: { open: boolean; onClose: () => void; customer?: ComposeFor }) {
  const [box, setBox] = useState<MailboxInfo | null>(null);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [from, setFrom] = useState("");
  const [companyId, setCompanyId] = useState(customer?.id ?? "");
  const [companyName, setCompanyName] = useState(customer?.name ?? "");
  const [customers, setCustomers] = useState<Option[]>(customer ? [{ value: customer.id, label: customer.name }] : []);
  const [people, setPeople] = useState<Option[]>([]);
  const [to, setTo] = useState<string[]>([]);
  const [template, setTemplate] = useState("");
  const [note, setNote] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const picked = templates.find((t) => t.id === template) ?? null;
  const fill = (text: string) => text.replaceAll("{customer}", companyName || "the customer").replaceAll("{me}", "you").replaceAll("{contact}", "");

  // Opened: the person's mailboxes and approved emails, and who the customer's addresses are.
  useEffect(() => {
    if (!open) return;
    start(async () => {
      const [b, t] = await Promise.all([readMailbox(), listTemplates()]);
      setBox(b);
      setTemplates(t);
      setFrom((f) => f || b?.mailboxes[0]?.id || "");
    });
  }, [open]);

  useEffect(() => {
    if (!companyId) return setPeople([]);
    start(async () => {
      const c = await customerAddresses(companyId);
      if (!c) return;
      const found = [
        ...(c.email ? [{ value: c.email, label: `${c.name} · ${c.email}` }] : []),
        ...c.contacts.filter((x) => x.email).map((x) => ({ value: x.email!, label: `${x.name} · ${x.email}` })),
      ];
      setPeople(found);
      setTo((now) => (now.length ? now : found.slice(0, 1).map((f) => f.value)));
    });
  }, [companyId]);

  function searchCustomers(q: string) {
    start(async () => setCustomers((await findCustomers(q)).map((c) => ({ value: c.id, label: c.city ? `${c.name} · ${c.city}` : c.name }))));
  }

  function send() {
    if (to.length === 0) return setError("Who is it to?");
    start(async () => {
      const r = await sendEmail(
        picked
          ? { companyId: companyId || null, contactId: null, to, mailboxId: from || undefined, templateId: picked.id, note: note.trim() || undefined }
          : { companyId: companyId || null, contactId: null, to, mailboxId: from || undefined, subject: subject.trim(), body: body.trim() },
      );
      if (!r.ok) return setError(r.fields ? Object.values(r.fields)[0] : r.error);
      const via = box?.mailboxes.find((m) => m.id === from);
      toast.success("Email sent", { description: via ? `${r.data.subject}, from ${via.address} (${via.providerName})` : r.data.subject });
      setNote("");
      setSubject("");
      setBody("");
      setTemplate("");
      setError(null);
      if (!customer) {
        setCompanyId("");
        setCompanyName("");
        setTo([]);
      }
      onClose();
    });
  }

  const none = box !== null && box.mailboxes.length === 0;
  return (
    <Modal open={open} title="New email" onCancel={onClose} onOk={send} okText="Send" okButtonProps={{ disabled: none || !box }} confirmLoading={pending} width={640} destroyOnHidden={false}>
      {none ? (
        <p className="py-2 text-sm text-ink">
          Connect a mailbox first (Zoho Mail, Gmail, Outlook or any by SMTP), so emails go out from your own address:{" "}
          <Link href="/account/mailbox" className="underline">
            Mailbox
          </Link>
          .
        </p>
      ) : (
        <div className="space-y-4 pt-1">
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">From</span>
            <Select
              className="w-full"
              value={from || undefined}
              onChange={setFrom}
              loading={!box}
              options={(box?.mailboxes ?? []).map((m) => ({ value: m.id, label: `${m.address} · ${m.providerName}${m.isDefault ? " (default)" : ""}` }))}
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Customer</span>
            <Select
              className="w-full"
              value={companyId || undefined}
              onChange={(v, o) => {
                setCompanyId(v ?? "");
                setCompanyName(v ? String((o as Option | undefined)?.label ?? "").split(" · ")[0] : "");
                setTo([]);
              }}
              options={customers}
              disabled={Boolean(customer)}
              allowClear={!customer}
              onFocus={() => !customer && customers.length === 0 && searchCustomers("")}
              showSearch={{ filterOption: false, onSearch: searchCustomers }}
              placeholder="Who it's about: it's kept on their page"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">To</span>
            <Select mode="tags" className="w-full" value={to} onChange={setTo} options={people} placeholder="Type an address, or pick one" tokenSeparators={[",", " "]} />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Approved email</span>
            <Select className="w-full" value={template} onChange={setTemplate} options={[{ value: "", label: "None: write my own" }, ...templates.map((t) => ({ value: t.id, label: t.name }))]} />
          </label>
          {picked ? (
            <>
              <label className="block">
                <span className="mb-1.5 block text-sm text-ink">
                  Personal note <span className="text-ink-3">(optional, goes on top)</span>
                </span>
                <Input.TextArea rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={5000} placeholder="e.g. Good to see you at your office today." />
              </label>
              <div className="rounded-sheet border border-rule bg-bench px-3 py-2">
                <p className="text-meta text-ink-3">Sent as approved, so it can&apos;t be changed here</p>
                <p className="mt-1 font-medium text-ink">{fill(picked.subject)}</p>
                <p className="mt-1 whitespace-pre-line text-sm text-ink-2">{fill(picked.body)}</p>
              </div>
            </>
          ) : (
            <>
              <label className="block">
                <span className="mb-1.5 block text-sm text-ink">Subject</span>
                <Input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={200} />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm text-ink">Message</span>
                <Input.TextArea rows={8} value={body} onChange={(e) => setBody(e.target.value)} maxLength={20000} />
              </label>
            </>
          )}
          <FormError message={error} />
        </div>
      )}
    </Modal>
  );
}
