"use client";

import { Input, Modal, Select } from "antd";
import Link from "next/link";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";
import { FormError } from "@/src/platform/ui/field";
import { findCustomers } from "../../actions/deals";
import { customerAddresses, listTemplates, prepareEmail, readMailbox, sendEmail, type EmailDraft, type EmailTemplate, type MailboxInfo } from "../../actions/mailbox";
import { OwnAppSend } from "./own-app-send";

type Option = { value: string; label: string };
export type ComposeFor = { id: string; name: string };

/**
 * Writing an email in the CRM. It goes out through the provider of the mailbox
 * picked in From (Zoho Mail, Gmail, Outlook, or any by SMTP), and is kept on
 * the customer. An approved email is sent as approved, with a personal note on
 * top; or the person writes their own.
 *
 * When the CRM can't send it (no mailbox connected, or the provider refused),
 * the same email is copied into the person's own email app instead, and logged
 * with a screenshot of it sent (own-app-send.tsx).
 */
export function Composer({ open, onClose, customer }: { open: boolean; onClose: () => void; customer?: ComposeFor }) {
  const [box, setBox] = useState<MailboxInfo | null>(null);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [from, setFrom] = useState("");
  const [companyId, setCompanyId] = useState(customer?.id ?? "");
  const [companyName, setCompanyName] = useState(customer?.name ?? "");
  const [customers, setCustomers] = useState<Option[]>(customer ? [{ value: customer.id, label: customer.name }] : []);
  const [people, setPeople] = useState<Option[]>([]);
  // The customer's addresses have been looked up (so "none saved" can be said).
  const [looked, setLooked] = useState(false);
  const [to, setTo] = useState<string[]>([]);
  const [template, setTemplate] = useState("");
  const [note, setNote] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  // Sending from the person's own email app: the email as it goes, once prepared.
  const [own, setOwn] = useState<{ draft: EmailDraft; ready: { to: string[]; subject: string; body: string } } | null>(null);
  const [failed, setFailed] = useState(false);
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
    setLooked(false);
    if (!companyId) return setPeople([]);
    let current = true;
    start(async () => {
      const c = await customerAddresses(companyId);
      // Another customer was picked meanwhile: this answer is for the old one.
      if (!c || !current) return;
      const found = [
        ...(c.email ? [{ value: c.email, label: `${c.name} · ${c.email}` }] : []),
        ...c.contacts.filter((x) => x.email).map((x) => ({ value: x.email!, label: `${x.name} · ${x.email}` })),
      ];
      setPeople(found);
      setLooked(true);
      setTo((now) => (now.length ? now : found.slice(0, 1).map((f) => f.value)));
      if (found.length) setError((e) => (e === "Who is it to?" ? null : e));
    });
    return () => {
      current = false;
    };
  }, [companyId]);

  function searchCustomers(q: string) {
    start(async () => setCustomers((await findCustomers(q)).map((c) => ({ value: c.id, label: [c.name, c.email ?? "no email saved", c.city].filter(Boolean).join(" · ") }))));
  }

  const draft = (): EmailDraft =>
    picked
      ? { companyId: companyId || null, contactId: null, to, templateId: picked.id, note: note.trim() || undefined }
      : { companyId: companyId || null, contactId: null, to, subject: subject.trim(), body: body.trim() };

  /** To the two steps: copy it into your own email, then log it with a screenshot. */
  function ownApp() {
    if (to.length === 0) return setError("Who is it to?");
    start(async () => {
      const d = draft();
      const r = await prepareEmail(d);
      if (!r.ok) return setError(r.fields ? Object.values(r.fields)[0] : r.error);
      setError(null);
      setOwn({ draft: d, ready: r.data });
    });
  }

  function reset() {
    setNote("");
    setSubject("");
    setBody("");
    setTemplate("");
    setError(null);
    setOwn(null);
    setFailed(false);
    if (!customer) {
      setCompanyId("");
      setCompanyName("");
      setTo([]);
    }
  }

  function send() {
    if (to.length === 0) return setError("Who is it to?");
    start(async () => {
      const r = await sendEmail({ ...draft(), mailboxId: from || undefined });
      if (!r.ok) {
        // Not a mistake in the email: the provider wouldn't send it. Offer the other way.
        setFailed(!r.fields);
        return setError(r.fields ? Object.values(r.fields)[0] : r.error);
      }
      const via = box?.mailboxes.find((m) => m.id === from);
      toast.success("Email sent", { description: via ? `${r.data.subject}, from ${via.address} (${via.providerName})` : r.data.subject });
      reset();
      onClose();
    });
  }

  const none = box !== null && box.mailboxes.length === 0;
  return (
    <Modal
      open={open}
      title={own ? "Send it from your own email" : "New email"}
      onCancel={() => {
        setOwn(null);
        onClose();
      }}
      onOk={none ? ownApp : send}
      okText={none ? "Next: copy it into your email" : "Send"}
      okButtonProps={{ disabled: !box }}
      confirmLoading={pending}
      width={640}
      destroyOnHidden={false}
      footer={own ? null : undefined}
    >
      {own ? (
        <>
          <button type="button" onClick={() => setOwn(null)} className="mb-2 text-meta text-ink-2 hover:text-ink hover:underline">
            ← Back to the email
          </button>
          <OwnAppSend
            draft={own.draft}
            ready={own.ready}
            onLogged={() => {
              reset();
              onClose();
            }}
          />
        </>
      ) : (
        <div className="space-y-4 pt-1">
          {none ? (
            <p className="rounded-[14px] bg-mint px-4 py-3 text-sm text-ink-2">
              Your mailbox isn&apos;t connected, so you&apos;ll send this from your own email, then log it here with a screenshot.{" "}
              <Link href="/account/mailbox" className="font-semibold text-ink underline">
                Connect your mailbox
              </Link>{" "}
              to send from the CRM instead.
            </p>
          ) : (
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
          )}
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
            <Select
              mode="tags"
              className="w-full"
              value={to}
              onChange={(v) => {
                setTo(v);
                if (v.length) setError((e) => (e === "Who is it to?" ? null : e));
              }}
              options={people}
              placeholder="Type an address, or pick one"
              tokenSeparators={[",", " "]}
            />
            {looked && people.length === 0 && (
              <span className="mt-1 block text-meta text-ink-3">
                {companyName || "This customer"} has no email saved, nor do their contacts. Type the address; to keep it for next time, add it on their page.
              </span>
            )}
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
          {failed && !none && (
            <p className="text-sm text-ink-2">
              It didn&apos;t go through your mailbox.{" "}
              <button type="button" onClick={ownApp} className="font-semibold text-ink underline">
                Send it from your own email instead
              </button>
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}
