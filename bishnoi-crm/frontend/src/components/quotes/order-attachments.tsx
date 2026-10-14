"use client";

import { CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { TextButton } from "@/src/platform/ui/button";
import { FieldRow } from "@/src/platform/ui/dialog";
import { Input } from "@/src/platform/ui/field";
import { FileDrop } from "@/src/platform/ui/file-drop";
import { uploadForm, type LinkAsks } from "../../actions/quote-links";

// What an order link asks the customer to send, set by the rep: the
// prescription (always for Rx medicines), a guarantee letter when someone else
// pays, and documents the rep named. Each is its own upload.
//
// Where the server has storage ("direct"), a file goes straight there from the
// browser the moment it's chosen, on a signed form good for a few minutes and
// up to 10 MB, so sending the order is quick and isn't held to the 4.5 MB a
// request may carry. Without storage ("with-order"), the files go with the order.

export type Kind = "prescription" | "letter" | "document";
/** One file, ready to go: uploaded (key), or to send with the order (file). */
export type Sent = { kind: Kind; index: number; name: string; size: number; key?: string; file?: File; uploading?: boolean };
export type Letter = { number: string; issuedOn: string; amount: string };

export const MAX_DIRECT_BYTES = 10 * 1024 * 1024;
// What a request may carry (Next's server actions, and Vercel), files and order together.
export const MAX_WITH_ORDER_BYTES = 4 * 1024 * 1024;
const TYPES = ["image/jpeg", "image/png", "application/pdf"];

/** One upload: a drop area that, in direct mode, uploads at once and says how it went. */
function Slot({ label, kind, index, mode, company, token, onChange }: {
  label: string;
  kind: Kind;
  index: number;
  mode: "direct" | "with-order";
  company: string;
  token: string;
  onChange: (sent: Sent | null) => void;
}) {
  const [state, setState] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [problem, setProblem] = useState<string | null>(null);

  async function chosen(file: File | null) {
    setProblem(null);
    if (!file) {
      setState("idle");
      return onChange(null);
    }
    if (!TYPES.includes(file.type)) {
      setState("error");
      setProblem("Attach a photo (JPG or PNG) or a PDF.");
      return onChange(null);
    }
    if (mode === "with-order") {
      setState("done");
      return onChange({ kind, index, name: file.name, size: file.size, file });
    }
    setState("uploading");
    onChange({ kind, index, name: file.name, size: file.size, uploading: true });
    const form = await uploadForm(company, token, kind, index, file.type);
    if (!form.ok) {
      setState("error");
      setProblem(form.error);
      return onChange(null);
    }
    const body = new FormData();
    for (const [k, v] of Object.entries(form.data.fields)) body.append(k, v);
    body.append("file", file);
    try {
      const sent = await fetch(form.data.url, { method: "POST", body });
      if (!sent.ok) throw new Error(String(sent.status));
      setState("done");
      onChange({ kind, index, name: file.name, size: file.size, key: form.data.key });
    } catch {
      setState("error");
      setProblem("The file didn't upload. Check your connection, and attach it again.");
      onChange(null);
    }
  }

  return (
    <div>
      <FileDrop
        accept={TYPES.join(",")}
        note={`${label}: JPG, PNG or PDF, up to ${mode === "direct" ? "10 MB" : "4 MB in all"}`}
        maxBytes={mode === "direct" ? MAX_DIRECT_BYTES : MAX_WITH_ORDER_BYTES}
        busy={state === "uploading"}
        onFile={chosen}
        aria-label={label}
      />
      {state === "done" && mode === "direct" && (
        <p className="mt-1 flex items-center gap-1.5 text-meta text-filed">
          <CheckCircle2 className="size-3.5" aria-hidden /> Uploaded
        </p>
      )}
      {problem && <p className="mt-1 text-meta text-danger">{problem}</p>}
    </div>
  );
}

/** Everything the link asks for, under the order: each with its upload, the letter with its details. */
export function WhatToSend({ asks, rxNames, mode, company, token, sent, setSent, letter, setLetter }: {
  asks: LinkAsks;
  rxNames: string[];
  mode: "direct" | "with-order";
  company: string;
  token: string;
  sent: Record<string, Sent>;
  setSent: (update: (all: Record<string, Sent>) => Record<string, Sent>) => void;
  letter: Letter;
  setLetter: (l: Letter) => void;
}) {
  const [pages, setPages] = useState(1);
  const wantsPrescription = rxNames.length > 0 || asks.prescriptionAlways;
  if (!wantsPrescription && !asks.payer && asks.documents.length === 0) return null;
  const put = (key: string) => (s: Sent | null) =>
    setSent((all) => {
      const next = { ...all };
      if (s) next[key] = s;
      else delete next[key];
      return next;
    });
  return (
    <section aria-labelledby="send" className="mt-4 space-y-4 rounded-lg border border-rule bg-bench/60 p-3">
      <div>
        <h3 id="send" className="text-sm font-semibold text-ink">
          What to send with your order
        </h3>
        <p className="text-meta text-ink-3">Asked for by your representative. Clear photos are fine.</p>
      </div>
      {wantsPrescription && (
        <div>
          <p className="text-sm font-medium text-ink">Prescription</p>
          <p className="mb-2 text-meta text-ink-2">
            {rxNames.length > 0 ? `${rxNames.join(", ")} ${rxNames.length === 1 ? "needs" : "need"} a doctor's prescription. ` : ""}Attach each page. A pharmacist checks it before your order is prepared.
          </p>
          <div className="space-y-2">
            {Array.from({ length: pages }, (_, i) => (
              <Slot key={i} label={pages > 1 ? `Prescription, page ${i + 1}` : "Prescription"} kind="prescription" index={i} mode={mode} company={company} token={token} onChange={put(`prescription-${i}`)} />
            ))}
          </div>
          {pages < 3 && sent[`prescription-${pages - 1}`] && !sent[`prescription-${pages - 1}`].uploading && (
            <TextButton className="mt-2" onClick={() => setPages((n) => n + 1)}>
              Add another page
            </TextButton>
          )}
        </div>
      )}
      {asks.payer && (
        <div>
          <p className="text-sm font-medium text-ink">{asks.payer.name} guarantee letter</p>
          <p className="mb-2 text-meta text-ink-2">{asks.payer.name} pays for this order: attach the letter, and copy its details.</p>
          <Slot label="Guarantee letter" kind="letter" index={0} mode={mode} company={company} token={token} onChange={put("letter-0")} />
          <div className="mt-2 space-y-2">
            <label className="block">
              <span className="mb-1 block text-meta text-ink">Letter number</span>
              <Input value={letter.number} onChange={(e) => setLetter({ ...letter, number: e.target.value })} maxLength={60} placeholder="As printed on the letter" />
            </label>
            <FieldRow>
              <label className="block">
                <span className="mb-1 block text-meta text-ink">Date on the letter</span>
                <Input type="date" value={letter.issuedOn} onChange={(e) => setLetter({ ...letter, issuedOn: (e.target as HTMLInputElement).value })} />
              </label>
              <label className="block">
                <span className="mb-1 block text-meta text-ink">Amount it covers (₱)</span>
                <Input value={letter.amount} onChange={(e) => setLetter({ ...letter, amount: e.target.value.replace(/[^\d.]/g, "") })} inputMode="decimal" placeholder="0.00" />
              </label>
            </FieldRow>
          </div>
        </div>
      )}
      {asks.documents.map((label, i) => (
        <div key={label}>
          <p className="mb-1 text-sm font-medium text-ink">{label}</p>
          <Slot label={label} kind="document" index={i} mode={mode} company={company} token={token} onChange={put(`document-${i}`)} />
        </div>
      ))}
    </section>
  );
}

/** Why the order can't be sent yet, for what the link asks: null when everything is there. */
export function whatsMissing(asks: LinkAsks, rxNames: string[], sent: Record<string, Sent>, letter: Letter, mode: "direct" | "with-order"): string | null {
  const files = Object.values(sent);
  if (files.some((f) => f.uploading)) return "Wait for your files to finish uploading.";
  if ((rxNames.length > 0 || asks.prescriptionAlways) && !files.some((f) => f.kind === "prescription"))
    return rxNames.length > 0 ? `Attach the prescription for ${rxNames.join(", ")}.` : "Attach your prescription.";
  if (asks.payer) {
    if (!sent["letter-0"]) return `Attach the ${asks.payer.name} guarantee letter.`;
    if (!letter.number.trim() || !letter.issuedOn || !(Number(letter.amount) > 0)) return "Give the guarantee letter's number, date and the amount it covers.";
  }
  const doc = asks.documents.findIndex((_, i) => !sent[`document-${i}`]);
  if (doc >= 0) return `Attach your ${asks.documents[doc]}.`;
  if (mode === "with-order" && files.reduce((n, f) => n + f.size, 0) > MAX_WITH_ORDER_BYTES) return "Your files are over 4 MB together. Take the photos again at a lower size.";
  return null;
}
