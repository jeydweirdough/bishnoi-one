"use client";

import { Dropdown, Modal } from "antd";
import { Check, Copy, Link2, MoreHorizontal } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, IconButton } from "@/src/platform/ui/button";
import { DialogPanel, FieldRow } from "@/src/platform/ui/dialog";
import { FormError } from "@/src/platform/ui/field";
import { Pill } from "@/src/platform/ui/figures";
import { Combobox } from "@/src/platform/ui/pickers";
import { changeQuoteLink, deleteQuoteLink, makeQuoteLink, quoteLinks, type QuoteLink, type QuoteLinks } from "../../actions/quote-links";

const LIFETIMES = [1, 4, 24, 72, 168];
const LIFETIME_WORDS: Record<number, string> = { 1: "1 hour", 4: "4 hours", 24: "1 day", 72: "3 days", 168: "1 week" };
const STATE = { open: { text: "Open", tone: "good" }, used: { text: "Used", tone: "plain" }, expired: { text: "Expired", tone: "plain" }, switched_off: { text: "Switched off", tone: "plain" } } as const;
const when = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });

type Choices = Pick<QuoteLinks, "priceTypes" | "lifetimes">;

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
  const [made, setMade] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const reload = () => start(async () => setData(await quoteLinks(companyId)));

  function show() {
    setOpen(true);
    setMade(null);
    setError(null);
    reload();
  }

  function make() {
    setError(null);
    start(async () => {
      const r = await makeQuoteLink(companyId, hours, priceType);
      if (!r.ok) return setError(r.error);
      setMade(`${window.location.origin}/order/${slug}/${r.data.token}`);
      setCopied(false);
      setData(await quoteLinks(companyId));
      onMade?.();
    });
  }

  async function copy() {
    if (!made) return;
    await navigator.clipboard.writeText(made).catch(() => null);
    setCopied(true);
    toast.success("Link copied", { description: "Send it: it works once." });
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
          <DialogPanel title="Send this link" hint="It's shown once. If it's lost, delete it below and make another.">
            <div className="flex items-center gap-2">
              <input readOnly value={made} onFocus={(e) => e.currentTarget.select()} className="min-w-0 flex-1 rounded-full border border-rule-strong bg-bench px-4 py-2 text-sm text-ink" aria-label="The order link" />
              <Button variant="primary" icon={copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />} onClick={copy}>
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
          </DialogPanel>
        ) : (
          <div className="mt-5 space-y-4">
            <LinkFields choices={data} hours={hours} setHours={setHours} priceType={priceType} setPriceType={setPriceType} />
            <FormError message={error} />
            <div className="dialog-actions">
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="primary" loading={pending} disabled={!data?.priceTypes.length} onClick={make}>
                Make the link
              </Button>
            </div>
          </div>
        )}

        {companyId && (data?.items.length ?? 0) > 0 && (
          <section className="mt-6">
            <p className="mb-2 text-sm font-medium text-ink">Links made lately</p>
            <LinkList links={data!.items} choices={data} onChanged={reload} />
          </section>
        )}
      </Modal>
    </>
  );
}

/**
 * Links, newest first: until when each works (or when it was used), whose it
 * is, its quote, and beside it the ⋯ to change it, switch it off or on, or delete it.
 */
export function LinkList({ links, choices, onChanged, showCustomer = false }: { links: QuoteLink[]; choices: Choices | null; onChanged: () => void; showCustomer?: boolean }) {
  const [editing, setEditing] = useState<QuoteLink | null>(null);
  const [deleting, setDeleting] = useState<QuoteLink | null>(null);
  const [pending, start] = useTransition();

  function flip(l: QuoteLink, on: boolean) {
    start(async () => {
      const r = await changeQuoteLink(l.id, { on });
      if (!r.ok) return void toast.error(r.error);
      toast.success(on ? "Link switched on" : "Link switched off");
      onChanged();
    });
  }

  return (
    <>
      <ul className="divide-y divide-rule rounded-[18px] border border-rule bg-sheet">
        {links.map((l) => (
          <li key={l.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
            <span className="min-w-0">
              <span className="block text-sm text-ink">
                {showCustomer && (
                  <span className="font-medium">
                    {l.customer ? (
                      <a href={`/companies/${l.customer.id}`} className="hover:underline">
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
                    <a href={`/quotes/${l.quoteId}`} className="text-ink hover:underline">
                      its quote
                    </a>
                  </>
                )}
              </span>
            </span>
            <span className="flex shrink-0 items-center gap-2">
              <Pill tone={STATE[l.state].tone}>{STATE[l.state].text}</Pill>
              <Dropdown
                trigger={["click"]}
                placement="bottomRight"
                menu={{
                  items: [
                    ...(l.state !== "used" ? [{ key: "change", label: l.state === "expired" ? "Give it more time" : "Change" }] : []),
                    ...(l.state === "open" ? [{ key: "off", label: "Switch off" }] : []),
                    ...(l.state === "switched_off" ? [{ key: "on", label: "Switch on" }] : []),
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
                <IconButton label="Change, switch off or delete this link" disabled={pending}>
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
