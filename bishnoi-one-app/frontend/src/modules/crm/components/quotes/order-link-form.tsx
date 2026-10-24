"use client";

import { CheckCircle2, LocateFixed, ShieldCheck, X } from "lucide-react";
import { Modal } from "antd";
import { useCallback, useEffect, useState } from "react";
import { Button, TextButton } from "@/src/platform/ui/button";
import { Input } from "@/src/platform/ui/field";
import { FieldRow } from "@/src/platform/ui/dialog";
import { addressAt, placeOrder, type LinkAsks, type NewCustomer, type Placed } from "@/src/modules/crm/actions/quote-links";
import { MedicineSearch, type Medicine } from "@/src/modules/crm/components/quotes/medicine-search";
import { WhatToSend, whatsMissing, type Letter, type Sent } from "@/src/modules/crm/components/quotes/order-attachments";

/**
 * The customer's side of an order link: first the privacy notice (what an
 * order shares, and why), then pick and send, then what happens next. No
 * prices here: they come in the quotation letter, after the order is sent.
 */
export function OrderLinkForm({ company, orgName, token, medicines, rep, asksWho = false, asks, uploads }: {
  company: string;
  orgName: string;
  token: string;
  medicines: Medicine[];
  rep: string;
  asksWho?: boolean;
  /** What the rep's link asks the customer to send. */
  asks: LinkAsks;
  /** Files straight to storage, or with the order (no storage on this server). */
  uploads: "direct" | "with-order";
}) {
  const [agreed, setAgreed] = useState(false);
  const [placed, setPlaced] = useState<Placed | null>(null);
  const [who, setWho] = useState<NewCustomer>({ name: "", contactName: null, mobile: null, email: null, address: null, city: null, latitude: null, longitude: null });
  const [locating, setLocating] = useState<"idle" | "asking" | "finding" | "refused">("idle");
  // Filled in from the shared location: said so, to be checked.
  const [filledFrom, setFilledFrom] = useState<"location" | "nothing" | null>(null);
  const [pickedIds, setPickedIds] = useState<string[]>([]);
  const onPick = useCallback((ids: string[]) => setPickedIds(ids), []);
  // What the link asks them to send: files by slot ("prescription-0", "letter-0", "document-1"), and the letter's details.
  const [sent, setSent] = useState<Record<string, Sent>>({});
  const [letter, setLetter] = useState<Letter>({ number: "", issuedOn: "", amount: "" });
  const rxNames = medicines.filter((m) => m.rx && pickedIds.includes(m.id)).map((m) => m.name);
  const set = (k: keyof NewCustomer) => (e: { target: { value: string } }) => setWho((w) => ({ ...w, [k]: e.target.value || null }));
  const first = rep.split(" ")[0];
  // Someone not a customer yet: who they are, a way to reach them, and where to deliver.
  const missing = whatsMissing(asks, rxNames, sent, letter, uploads) ?? (!asksWho
    ? null
    : who.name.trim().length < 2
      ? "Fill in your name, or your business's."
      : !(who.mobile?.trim() || who.email?.trim())
        ? `Give a mobile number or an email, so ${first} can reach you.`
        : !(who.address?.trim() && who.city?.trim())
          ? "Give the delivery address and city."
          : null);

  /** The browser asks the person first; nothing is taken unless they say yes. */
  function locate() {
    if (!("geolocation" in navigator)) return setLocating("refused");
    setLocating("asking");
    navigator.geolocation.getCurrentPosition(
      async (p) => {
        const latitude = Math.round(p.coords.latitude * 1e6) / 1e6;
        const longitude = Math.round(p.coords.longitude * 1e6) / 1e6;
        setWho((w) => ({ ...w, latitude, longitude }));
        setLocating("finding");
        const at = await addressAt(company, token, latitude, longitude);
        // What they typed stays: only empty fields are filled in.
        setWho((w) => ({ ...w, address: w.address?.trim() ? w.address : at.address, city: w.city?.trim() ? w.city : at.city }));
        setFilledFrom(at.address || at.city ? "location" : "nothing");
        setLocating("idle");
      },
      () => setLocating("refused"),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  }

  if (placed) {
    return (
      <section className="mx-auto max-w-xl rounded-sheet border border-rule bg-sheet p-6 text-center">
        <CheckCircle2 className="mx-auto size-10 text-filed" aria-hidden />
        <h2 className="mt-3 text-heading text-ink">Your order is in: quotation {placed.number}</h2>
        <p className="mt-1 text-sm text-ink-2">
          {placed.rep} has it, and sends you the quotation letter with the prices{placed.waitsForApproval ? " once they're reviewed" : ""}.
        </p>
        <ul className="mt-5 divide-y divide-rule text-left text-sm">
          {placed.lines.map((l, i) => (
            <li key={i} className="flex justify-between gap-3 py-2">
              <span>{l.name}</span>
              <span className="tabular-nums">× {l.quantity}</span>
            </li>
          ))}
        </ul>
        <p className="mt-5 text-meta text-ink-3">This link is used now. To order again, ask {placed.rep} for a new one.</p>
      </section>
    );
  }
  return (
    <>
      {/* Floating over the order until they agree: what they'll fill in is in view, and out of reach. */}
      <PrivacyNotice open={!agreed} orgName={orgName} rep={rep} asksWho={asksWho} asks={asks} onAgree={() => setAgreed(true)} />
      <div inert={!agreed} aria-hidden={!agreed} className={agreed ? "" : "pointer-events-none select-none"}>
        <MedicineSearch
          medicines={medicines}
          submitLabel={`Send my order to ${first}`}
          withNote
          showPrices={false}
          missing={missing}
          onPick={onPick}
          extra={<WhatToSend asks={asks} rxNames={rxNames} mode={uploads} company={company} token={token} sent={sent} setSent={setSent} letter={letter} setLetter={setLetter} />}
          before={
            asksWho && (
              <div>
                <h2 className="text-heading text-ink">About you</h2>
                <p className="mt-0.5 text-meta text-ink-3">So {first} knows who the order is for, how to reach you, and where to deliver.</p>
                <div className="mt-3 space-y-3">
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-ink">Your name, or your business&apos;s</span>
                    <Input value={who.name} onChange={(e) => setWho((w) => ({ ...w, name: e.target.value }))} maxLength={160} placeholder="e.g. Maria Santos, or St. Luke's Pharmacy" autoComplete="organization" />
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-ink">
                      Contact person <span className="font-normal text-ink-3">(optional)</span>
                    </span>
                    <Input value={who.contactName ?? ""} onChange={set("contactName")} maxLength={160} autoComplete="name" />
                  </label>
                  <FieldRow>
                    <label className="block">
                      <span className="mb-1.5 block text-sm font-medium text-ink">Mobile</span>
                      <Input value={who.mobile ?? ""} onChange={set("mobile")} maxLength={40} inputMode="tel" autoComplete="tel" placeholder="0917 123 4567" />
                    </label>
                    <label className="block">
                      <span className="mb-1.5 block text-sm font-medium text-ink">Email</span>
                      <Input value={who.email ?? ""} onChange={set("email")} maxLength={254} type="email" autoComplete="email" />
                    </label>
                  </FieldRow>
                  {/* Optional: a pin helps the delivery find the place, and fills in the address. Asked by the browser, never taken quietly. */}
                  <div className="rounded-lg bg-bench px-3 py-2.5">
                    {who.latitude !== null && locating !== "finding" ? (
                      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-ink-2">
                        <LocateFixed className="size-4 text-sage-deep" aria-hidden />
                        {filledFrom === "location"
                          ? "Location added. The address below is filled in from it: check it, and add the house or building."
                          : "Location added, for the delivery. Its address couldn't be found: type it below."}
                        <TextButton tone="muted" onClick={() => (setWho((w) => ({ ...w, latitude: null, longitude: null })), setFilledFrom(null))}>
                          <X className="size-3.5" aria-hidden /> Remove
                        </TextButton>
                      </p>
                    ) : (
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <Button size="sm" icon={<LocateFixed className="size-3.5" aria-hidden />} onClick={locate} loading={locating === "asking" || locating === "finding"}>
                          {locating === "finding" ? "Finding the address" : "Use my location"}
                        </Button>
                        <span className="text-meta text-ink-3">
                          {locating === "refused" ? "Your location wasn't shared. Type the address below." : "Optional: fills in the address, and helps the delivery find you. Your browser asks first."}
                        </span>
                      </div>
                    )}
                  </div>
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-ink">Delivery address</span>
                    <Input value={who.address ?? ""} onChange={set("address")} maxLength={300} autoComplete="street-address" placeholder="House or building, street, barangay" />
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-ink">City or municipality</span>
                    <Input value={who.city ?? ""} onChange={set("city")} maxLength={80} autoComplete="address-level2" placeholder="e.g. Quezon City" />
                  </label>
                </div>
              </div>
            )
          }
          onSubmit={async (lines, note) => {
            if (!agreed) return "Agree to the privacy notice first.";
            const files = Object.values(sent).sort((a, b) => a.kind.localeCompare(b.kind) || a.index - b.index);
            const form = new FormData();
            form.set(
              "order",
              JSON.stringify({
                lines,
                note,
                customer: asksWho ? { ...who, name: who.name.trim() } : null,
                privacyAccepted: true,
                // Uploaded straight to storage: what each is, and where it went.
                files: files.filter((f) => f.key).map((f) => ({ kind: f.kind, index: f.index, key: f.key, name: f.name })),
                letter: asks.payer ? { number: letter.number.trim(), issuedOn: letter.issuedOn, amountCentavos: Math.round(Number(letter.amount) * 100) } : null,
              }),
            );
            // No storage on this server: the files themselves, with the order.
            for (const f of files.filter((x) => x.file)) form.append(f.kind === "letter" ? "letter_file" : f.kind, f.file!, f.name);
            const r = await placeOrder(company, token, form);
            if (!r.ok) return r.error;
            setPlaced(r.data);
            return null;
          }}
        />
      </div>
    </>
  );
}

/**
 * Before anything is asked: what an order shares, why, who sees it, and the
 * person's rights under the Data Privacy Act of 2012 (Republic Act 10173).
 * A medicine order is health information, sensitive personal information under
 * the Act, so it's asked for every order, and only with a yes.
 */
function PrivacyNotice({ open, orgName, rep, asksWho, asks, onAgree }: { open: boolean; orgName: string; rep: string; asksWho: boolean; asks: LinkAsks; onAgree: () => void }) {
  // What this link asks for, said in the notice too: a prescription is health information, an ID is personal.
  const papers = ["your prescription, if a medicine needs one" + (asks.prescriptionAlways ? " (asked with every order)" : ""), asks.payer ? `the ${asks.payer.name} guarantee letter` : "", ...asks.documents.map((d) => `your ${d}`)].filter(Boolean);
  const [ticked, setTicked] = useState(false);
  // Opened once the page is live in the browser: the dialog lives in a layer the server doesn't draw.
  const [live, setLive] = useState(false);
  useEffect(() => setLive(true), []);
  return (
    // Only a yes closes it: no ✕, no click outside, no Escape.
    <Modal
      open={open && live}
      centered
      width={640}
      closable={false}
      mask={{ closable: false }}
      keyboard={false}
      footer={null}
      aria-labelledby="privacy"
      styles={{ mask: { backdropFilter: "blur(3px)" }, body: { maxHeight: "min(70dvh, 46rem)", overflowY: "auto" } }}
    >
      <span className="grid size-11 place-items-center rounded-lg bg-hema-tint text-sage-deep">
        <ShieldCheck className="size-5" aria-hidden />
      </span>
      <h2 id="privacy" className="mt-4 text-heading text-ink">
        Before you order: your privacy
      </h2>
      <p className="mt-1 text-sm text-ink-2">
        {orgName} keeps your information safe, as the Data Privacy Act of 2012 (Republic Act 10173) requires. Here is what your order shares, and why.
      </p>
      <dl className="mt-5 space-y-3 text-sm">
        <div>
          <dt className="font-semibold text-ink">What we collect</dt>
          <dd className="text-ink-2">
            The medicines and quantities you order, {papers.join(", ")}
            {asksWho ? ", your name or your business's, a contact person, your mobile number or email, your delivery address and, only if you choose to share it, your location" : ""}. Files are kept privately and seen only by those below.
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-ink">Why</dt>
          <dd className="text-ink-2">To prepare your quotation, contact you about it, and deliver your order. Nothing else, and we never sell it.</dd>
        </div>
        <div>
          <dt className="font-semibold text-ink">Who sees it</dt>
          <dd className="text-ink-2">
            {orgName} and {rep}, your medical representative. It is shared with a courier only to deliver your order, and with authorities only where the law requires.
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-ink">How long we keep it</dt>
          <dd className="text-ink-2">For as long as your order and our records under Philippine law need it, then it is deleted.</dd>
        </div>
        <div>
          <dt className="font-semibold text-ink">Your rights</dt>
          <dd className="text-ink-2">
            You may ask to see, correct or delete your information, or withdraw your consent, by telling {rep}. You may also complain to the National Privacy Commission (privacy.gov.ph).
          </dd>
        </div>
      </dl>
      <label className="mt-6 flex cursor-pointer items-start gap-3 rounded-lg border border-rule px-4 py-3 has-[:checked]:border-sage has-[:checked]:bg-mint">
        <input suppressHydrationWarning type="checkbox" checked={ticked} onChange={(e) => setTicked(e.target.checked)} className="mt-0.5 size-4 accent-[#141414]" />
        <span className="text-sm text-ink">I have read this, and I agree to {orgName} using my information for my order, as described.</span>
      </label>
      <Button variant="primary" className="mt-4 w-full" disabled={!ticked} onClick={onAgree}>
        Continue to my order
      </Button>
    </Modal>
  );
}
