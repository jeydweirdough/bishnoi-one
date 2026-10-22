import type { SignedStep } from "./types";

// The signature lines at the foot of a printed document (journal voucher, liquidation
// report). Each line is a step: who did it, with the signature they had then, when, and
// a reference to what they signed (the start of its fingerprint). A step not done yet
// is an empty line. Decided 2026-10-22 (Plans/Plan - E-signatures).

const when = (iso: string, timeZone: string) =>
  new Intl.DateTimeFormat("en-PH", { timeZone, day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(iso));

export function SignatureLines({ lines, signed, timeZone }: { lines: { step: string; label: string }[]; signed: SignedStep[]; timeZone: string }) {
  return (
    <div className="mt-10 grid gap-8 sm:grid-cols-2 print:grid-cols-2">
      {lines.map((line) => {
        // The latest of that step (an entry approved once; a step redone keeps its newest).
        const s = [...signed].reverse().find((x) => x.step === line.step);
        return (
          <div key={line.step} className="break-inside-avoid">
            <p className="text-meta text-ink-3">{line.label}</p>
            <div className="flex h-16 items-end">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {s?.image && <img src={s.image} alt={`${s.name}'s signature`} className="max-h-16 max-w-64 object-contain" />}
            </div>
            <div className="border-t border-ink pt-1">
              <p className="text-sm font-semibold">{s ? s.name : " "}</p>
              <p className="text-meta text-ink-3">
                {s ? (
                  <>
                    {s.role} · {when(s.at, timeZone)}
                    <br />
                    {s.image ? "Signed electronically" : "No e-signature set at the time"} · Ref. {s.ref}
                  </>
                ) : (
                  "Not yet"
                )}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
