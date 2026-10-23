"use client";

import { Dropdown, Modal } from "antd";
import { Check, Copy, Link2, MoreHorizontal, Plus, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, IconButton } from "@/src/platform/ui/button";
import { DialogPanel, FieldRow } from "@/src/platform/ui/dialog";
import { FormError, Input } from "@/src/platform/ui/field";
import { Pill } from "@/src/platform/ui/figures";
import { Combobox } from "@/src/platform/ui/pickers";
import { changeQuoteLink, deleteQuoteLink, makeQuoteLink, quoteLinks, quoteLinkToken, type AsksInput, type LinkAsks, type QuoteLink, type QuoteLinks } from "@/src/modules/crm/actions/quote-links";

const LIFETIMES = [1, 4, 24, 72, 168];
const LIFETIME_WORDS: Record<number, string> = { 1: "1 hour", 4: "4 hours", 24: "1 day", 72: "3 days", 168: "1 week" };
const STATE = { open: { text: "Open", tone: "good" }, used: { text: "Used", tone: "plain" }, expired: { text: "Expired", tone: "plain" }, switched_off: { text: "Inactive", tone: "plain" } } as const;
const when = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });

type Choices = Pick<QuoteLinks, "priceTypes" | "lifetimes"> & Partial<Pick<QuoteLinks, "payers">>;

// The documents a rep asks for most, one tap each.
const COMMON_DOCUMENTS = ["Valid ID", "Senior citizen card", "PWD ID", "Medical abstract", "Doctor's request"];
const NO_ASKS: AsksInput = { prescriptionAlways: false, payer: null, documents: [] };

/** What the link asks for, in a line: "Prescription, DSWD guarantee letter, Valid ID". */
export function asksWords(asks: LinkAsks | undefined): string {
  if (!asks) return "";
  return [asks.prescriptionAlways ? "a prescription" : "", asks.payer ? `${asks.payer.name} guarantee letter` : "", ...asks.documents].filter(Boolean).join(", ");
}

/**
 * What the customer sends with the order: a prescription (always asked for Rx
 * medicines; here, for any order), a guarantee letter when someone else pays,
 * and documents the rep names. The customer is asked for exactly these.
 */
function AsksFields({ choices, asks, setAsks }: { choices: Choices | null; asks: AsksInput; setAsks: (a: AsksInput) => void }) {
  const [typed, setTyped] = useState("");
  const add = (label: string) => {
    const clean = label.trim().replace(/\s+/g, " ").slice(0, 60);
    if (!clean || asks.documents.length >= 5 || asks.documents.some((d) => d.toLowerCase() === clean.toLowerCase())) return;
    setAsks({ ...asks, documents: [...asks.documents, clean] });
    setTyped("");
  };
  return (
    <section className="rounded-xl border border-rule p-4">
      <p className="text-sm font-semibold text-ink">Required documents</p>
      <p className="text-meta text-ink-3">They&apos;re asked for exactly these, and can&apos;t send the order without them. Rx medicines always need a prescription.</p>
      <label className="mt-3 flex cursor-pointer items-start gap-3">
        <input type="checkbox" checked={asks.prescriptionAlways} onChange={(e) => setAsks({ ...asks, prescriptionAlways: e.target.checked })} className="mt-0.5 size-4 accent-[#141414]" />
        <span className="text-sm text-ink">Ask for a prescription with every order, Rx or not</span>
      </label>
      {(choices?.payers?.length ?? 0) > 0 && (
        <label className="mt-3 block">
          <span className="mb-1.5 block text-sm text-ink">Payer</span>
          <Combobox
            value={asks.payer ?? ""}
            onChange={(v: string) => setAsks({ ...asks, payer: v || null })}
            options={[{ value: "", label: "Customer (self-pay)" }, ...choices!.payers!.map((p) => ({ value: p.code, label: `${p.name}: they attach the guarantee letter` }))]}
          />
        </label>
      )}
      <div className="mt-3">
        <span className="mb-1.5 block text-sm text-ink">Documents to attach <span className="text-ink-3">(up to 5)</span></span>
        {asks.documents.length > 0 && (
          <ul className="mb-2 flex flex-wrap gap-1.5">
            {asks.documents.map((d) => (
              <li key={d} className="inline-flex h-7 items-center gap-1 rounded-md bg-hema-tint pr-1 pl-3 text-meta text-ink">
                {d}
                <button type="button" aria-label={`Don't ask for ${d}`} onClick={() => setAsks({ ...asks, documents: asks.documents.filter((x) => x !== d) })} className="grid size-5 place-items-center rounded-md hover:bg-sheet">
                  <X className="size-3" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
        {asks.documents.length < 5 && (
          <>
            <div className="flex gap-2">
              <Input value={typed} onChange={(e) => setTyped(e.target.value)} onPressEnter={() => add(typed)} placeholder="e.g. Valid ID" maxLength={60} aria-label="A document to ask for" />
              <Button icon={<Plus className="size-4" aria-hidden />} onClick={() => add(typed)} disabled={!typed.trim()}>
                Add
              </Button>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {COMMON_DOCUMENTS.filter((d) => !asks.documents.includes(d)).map((d) => (
                <button key={d} type="button" onClick={() => add(d)} className="h-7 rounded-md border border-dashed border-rule-strong px-3 text-meta text-ink-2 hover:border-ink hover:text-ink">
                  + {d}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

const address = (slug: string, token: string) => `${window.location.origin}/order/${slug}/${token}`;

async function copyText(text: string) {
  await navigator.clipboard.writeText(text).catch(() => null);
  toast.success("Link copied", { description: "Single-use link." });
}

/** How long it works, and which price it shows: the same two fields to make a link and to change one. */
function LinkFields({ choices, hours, setHours, priceType, setPriceType, hoursLabel = "How long it works" }: { choices: Choices | null; hours: number; setHours: (h: number) => void; priceType: string | null; setPriceType: (t: string) => void; hoursLabel?: string }) {
  return (
    <FieldRow>
      <label className="block">
        <span className="mb-1.5 block text-sm text-ink">{hoursLabel}</span>
        <Combobox value={hours} onChange={(v: number) => setHours(v)} options={(choices?.lifetimes ?? LIFETIMES).map((h) => ({ value: h, label: LIFETIME_WORDS[h] ?? `${h} hours` }))} />
      </label>
      <label className="block">
        <span className="mb-1.5 block text-sm text-ink">Their price</span>
        <Combobox
          value={priceType ?? choices?.priceTypes[0]?.code}
          onChange={(v: string) => setPriceType(v)}
          options={(choices?.priceTypes ?? []).map((t) => ({ value: t.code, label: t.name }))}
          placeholder={choices ? "No list prices" : "Getting the prices…"}
        />
      </label>
    </FieldRow>
  );
}

/**
 * "Order link": a link for this customer (or, with none, for someone not a
 * customer yet) to order from, at their own prices, that works once and only
 * until it expires. Made here, copied and sent; the order becomes a quote, the rep's.
 */
export function OrderLinkButton({ companyId = null, companyName = null, slug, label = "Order link", variant = "default", onMade }: { companyId?: string | null; companyName?: string | null; slug: string; label?: string; variant?: "primary" | "default"; onMade?: () => void }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<QuoteLinks | null>(null);
  const [hours, setHours] = useState(24);
  const [priceType, setPriceType] = useState<string | null>(null);
  const [asks, setAsks] = useState<AsksInput>(NO_ASKS);
  const [made, setMade] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const reload = () => start(async () => setData(await quoteLinks(companyId)));

  function show() {
    setOpen(true);
    setMade(null);
    setAsks(NO_ASKS);
    setError(null);
    reload();
  }

  function make() {
    setError(null);
    start(async () => {
      const r = await makeQuoteLink(companyId, hours, priceType, asks);
      if (!r.ok) return setError(r.error);
      setMade(address(slug, r.data.token));
      setCopied(false);
      setData(await quoteLinks(companyId));
      onMade?.();
    });
  }

  async function copy() {
    if (!made) return;
    await copyText(made);
    setCopied(true);
  }

  return (
    <>
      <Button variant={variant} icon={<Link2 className="size-4" aria-hidden />} onClick={show}>
        {label}
      </Button>
      <Modal open={open} title={companyName ? "Order link" : "New order link"} onCancel={() => setOpen(false)} footer={null} width={600} destroyOnHidden>
        <p className="text-sm text-ink-2">
          {companyName
            ? `A link ${companyName} opens to find their medicines, at their prices, and send an order: it becomes a quote, yours.`
            : "A link for someone not a customer yet: they say who they are, pick their medicines and send. They become your customer, and the order your quote."}{" "}
          It works once, until it expires; for the next order, make a new one.
        </p>

        {made ? (
          <DialogPanel title="Order link" hint="You can copy it again from the list while it works.">
            <div className="flex items-center gap-2">
              <input readOnly value={made} onFocus={(e) => e.currentTarget.select()} className="min-w-0 flex-1 rounded-lg border border-rule-strong bg-bench px-4 py-2 text-sm text-ink" aria-label="The order link" />
              <Button variant="primary" icon={copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />} onClick={copy}>
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
          </DialogPanel>
        ) : (
          <div className="mt-5 space-y-4">
            <LinkFields choices={data} hours={hours} setHours={setHours} priceType={priceType} setPriceType={setPriceType} />
            <AsksFields choices={data} asks={asks} setAsks={setAsks} />
            <FormError message={error} />
            <div className="dialog-actions">
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="primary" loading={pending} disabled={!data?.priceTypes.length} onClick={make}>
                Create link
              </Button>
            </div>
          </div>
        )}

        {companyId && (data?.items.length ?? 0) > 0 && (
          <section className="mt-6">
            <p className="mb-2 text-sm font-medium text-ink">Links made lately</p>
            <LinkList links={data!.items} choices={data} slug={slug} onChanged={reload} />
          </section>
        )}
      </Modal>
    </>
  );
}

/**
 * Links, newest first: until when each works (or when it was used), whose it
 * is, its quote, and beside it Copy (while it's open) and the ⋯ to change it,
 * switch it off or on, or delete it.
 */
export function LinkList({ links, choices, slug, onChanged, showCustomer = false }: { links: QuoteLink[]; choices: Choices | null; slug: string; onChanged: () => void; showCustomer?: boolean }) {
  const [editing, setEditing] = useState<QuoteLink | null>(null);
  const [deleting, setDeleting] = useState<QuoteLink | null>(null);
  const [pending, start] = useTransition();

  function copy(l: QuoteLink) {
    start(async () => {
      const r = await quoteLinkToken(l.id);
      if (!r.ok) return void toast.error(r.error);
      await copyText(address(slug, r.data.token));
    });
  }

  function flip(l: QuoteLink, on: boolean) {
    start(async () => {
      const r = await changeQuoteLink(l.id, { on });
      if (!r.ok) return void toast.error(r.error);
      toast.success(on ? "Link activated" : "Link deactivated");
      onChanged();
    });
  }

  return (
    <>
      <ul className="divide-y divide-rule rounded-xl border border-rule bg-sheet">
        {links.map((l) => (
          <li key={l.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
            <span className="min-w-0">
              <span className="block text-sm text-ink">
                {showCustomer && (
                  <span className="font-medium">
                    {l.customer ? (
                      <a href={`/crm/companies/${l.customer.id}`} className="hover:underline">
                        {l.customer.name}
                      </a>
                    ) : (
                      "For a new customer"
                    )}
                    {" · "}
                  </span>
                )}
                {l.state === "used" && l.usedAt ? `Ordered ${when.format(new Date(l.usedAt))}` : `Until ${when.format(new Date(l.expiresAt))}`}
              </span>
              <span className="block text-meta text-ink-3">
                By {l.owner.name}
                {l.quoteId && (
                  <>
                    {" · "}
                    <a href={`/crm/quotes/${l.quoteId}`} className="text-ink hover:underline">
                      its quote
                    </a>
                  </>
                )}
              </span>
              {asksWords(l.asks) && <span className="block text-meta text-ink-3">Asks for {asksWords(l.asks)}</span>}
            </span>
            <span className="flex shrink-0 items-center gap-2">
              <Pill tone={STATE[l.state].tone}>{STATE[l.state].text}</Pill>
              {l.state === "open" && (
                <Button size="sm" icon={<Copy className="size-3.5" aria-hidden />} disabled={pending} onClick={() => copy(l)}>
                  Copy link
                </Button>
              )}
              <Dropdown
                trigger={["click"]}
                placement="bottomRight"
                menu={{
                  items: [
                    ...(l.state !== "used" ? [{ key: "change", label: l.state === "expired" ? "Extend" : "Edit" }] : []),
                    ...(l.state === "open" ? [{ key: "off", label: "Deactivate" }] : []),
                    ...(l.state === "switched_off" ? [{ key: "on", label: "Activate" }] : []),
                    ...(l.state !== "used" ? [{ type: "divider" as const }] : []),
                    { key: "delete", label: "Delete", danger: true },
                  ],
                  onClick: ({ key }) => {
                    if (key === "change") setEditing(l);
                    if (key === "off") flip(l, false);
                    if (key === "on") flip(l, true);
                    if (key === "delete") setDeleting(l);
                  },
                }}
              >
                <IconButton label="Edit, deactivate or delete this link" disabled={pending}>
                  <MoreHorizontal className="size-4" aria-hidden />
                </IconButton>
              </Dropdown>
            </span>
          </li>
        ))}
      </ul>
      {editing && <ChangeLink link={editing} choices={choices} onDone={() => (setEditing(null), onChanged())} onCancel={() => setEditing(null)} />}
      <Modal
        open={deleting !== null}
        title="Delete this link?"
        okText="Delete link"
        okButtonProps={{ danger: true }}
        confirmLoading={pending}
        onCancel={() => setDeleting(null)}
        onOk={() =>
          deleting &&
          start(async () => {
            const r = await deleteQuoteLink(deleting.id);
            if (!r.ok) return void toast.error(r.error);
            toast.success("Link deleted");
            setDeleting(null);
            onChanged();
          })
        }
        width={440}
      >
        <p className="text-sm text-ink-2">
          {deleting?.quoteId ? "It goes from the list. The quote it made stays, on its customer." : "It goes from the list, and whoever has it can't open it any more."}
        </p>
      </Modal>
    </>
  );
}

/** Changing a link that hasn't been used: more time (from now), or another price. */
function ChangeLink({ link, choices, onDone, onCancel }: { link: QuoteLink; choices: Choices | null; onDone: () => void; onCancel: () => void }) {
  const [hours, setHours] = useState(24);
  const [priceType, setPriceType] = useState<string | null>(link.priceType);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  function save() {
    setError(null);
    start(async () => {
      const r = await changeQuoteLink(link.id, { hours, priceType: priceType ?? undefined, on: true });
      if (!r.ok) return setError(r.error);
      toast.success("Link changed", { description: `It works until ${when.format(new Date(r.data.expiresAt))}.` });
      onDone();
    });
  }
  return (
    <Modal open title={link.state === "expired" ? "Give the link more time" : "Change the link"} onCancel={onCancel} footer={null} width={560}>
      <p className="text-sm text-ink-2">The same link, still unused: whoever has it opens it again, with the time and price you set here.</p>
      <div className="mt-5 space-y-4">
        <LinkFields choices={choices} hours={hours} setHours={setHours} priceType={priceType} setPriceType={setPriceType} hoursLabel="Works for, from now" />
        <FormError message={error} />
        <div className="dialog-actions">
          <Button onClick={onCancel}>Cancel</Button>
          <Button variant="primary" loading={pending} onClick={save}>
            Save the change
          </Button>
        </div>
      </div>
    </Modal>
  );
}
