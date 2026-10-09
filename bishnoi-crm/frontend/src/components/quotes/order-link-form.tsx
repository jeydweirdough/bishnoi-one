"use client";

import { CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { Input } from "@/src/platform/ui/field";
import { FieldRow } from "@/src/platform/ui/dialog";
import { placeOrder, type NewCustomer, type Placed } from "../../actions/quote-links";
import { MedicineSearch, type Medicine } from "./medicine-search";

const peso = new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP" });

/** The customer's side of an order link: pick, send, and what happens next. */
export function OrderLinkForm({ company, token, medicines, rep, asksWho = false }: { company: string; token: string; medicines: Medicine[]; rep: string; asksWho?: boolean }) {
  const [placed, setPlaced] = useState<Placed | null>(null);
  const [who, setWho] = useState<NewCustomer>({ name: "", contactName: null, mobile: null, email: null, city: null });
  const set = (k: keyof NewCustomer) => (e: { target: { value: string } }) => setWho((w) => ({ ...w, [k]: e.target.value || null }));
  // Someone not a customer yet: who they are, and a way to reach them.
  const missing = !asksWho ? null : who.name.trim().length < 2 ? "Fill in your name, or your business's." : !(who.mobile?.trim() || who.email?.trim()) ? "Give a mobile number or an email, so your rep can reach you." : null;
  if (placed) {
    return (
      <section className="mx-auto max-w-xl rounded-sheet border border-rule bg-sheet p-6 text-center">
        <CheckCircle2 className="mx-auto size-10 text-filed" aria-hidden />
        <h2 className="mt-3 text-heading text-ink">Your order is in: quotation {placed.number}</h2>
        <p className="mt-1 text-sm text-ink-2">
          {placed.waitsForApproval
            ? `${placed.rep} has it: the prices are reviewed first, then you get the quotation letter.`
            : `${placed.rep} has it, and sends you the quotation letter.`}
        </p>
        <ul className="mt-5 divide-y divide-rule text-left text-sm">
          {placed.lines.map((l, i) => (
            <li key={i} className="flex justify-between gap-3 py-2">
              <span>
                {l.name} × {l.quantity}
              </span>
              <span className="tabular-nums">{peso.format(l.totalCentavos / 100)}</span>
            </li>
          ))}
          <li className="flex justify-between gap-3 py-2 font-semibold">
            <span>Total</span>
            <span className="tabular-nums">{peso.format(placed.totalCentavos / 100)}</span>
          </li>
        </ul>
        <p className="mt-5 text-meta text-ink-3">This link is used now. To order again, ask {placed.rep} for a new one.</p>
      </section>
    );
  }
  return (
    <MedicineSearch
      medicines={medicines}
      submitLabel={`Send my order to ${rep.split(" ")[0]}`}
      withNote
      withAsk
      missing={missing}
      before={
        asksWho && (
          <div>
            <h2 className="text-heading text-ink">About you</h2>
            <p className="mt-0.5 text-meta text-ink-3">So {rep.split(" ")[0]} knows who the order is for, and how to reach you.</p>
            <div className="mt-3 space-y-3">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-ink">Your name, or your business&apos;s</span>
                <Input value={who.name} onChange={(e) => setWho((w) => ({ ...w, name: e.target.value }))} maxLength={160} placeholder="e.g. Linus Aurin, or St. Luke's Pharmacy" autoComplete="organization" />
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
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-ink">
                  City <span className="font-normal text-ink-3">(optional)</span>
                </span>
                <Input value={who.city ?? ""} onChange={set("city")} maxLength={80} autoComplete="address-level2" />
              </label>
            </div>
          </div>
        )
      }
      onSubmit={async (lines, note) => {
        const r = await placeOrder(company, token, lines, note, asksWho ? { ...who, name: who.name.trim() } : null);
        if (!r.ok) return r.error;
        setPlaced(r.data);
        return null;
      }}
    />
  );
}
