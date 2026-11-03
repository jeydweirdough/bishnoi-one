"use client";

import { Download, KeyRound, QrCode } from "lucide-react";
import { useEffect, useState, useTransition, type ReactNode } from "react";
import { Button } from "@/src/platform/ui/ant-button";
import { Field, FormError, Input, PasswordInput } from "@/src/platform/ui/field";
import { confirmTwoStep, startTwoStep, type TwoStepStart } from "./actions";
import { RecoveryCodes } from "./sign-in-forms";

const STEPS: { icon: ReactNode; title: string; text: string }[] = [
  { icon: <Download className="size-5" aria-hidden />, title: "Install an authenticator app", text: "Google Authenticator, Microsoft Authenticator or 1Password, on your phone." },
  { icon: <QrCode className="size-5" aria-hidden />, title: "Scan the code", text: "In the app, add an account and scan the QR code on this page." },
  { icon: <KeyRound className="size-5" aria-hidden />, title: "Enter the six digits", text: "The app shows a new code every 30 seconds. You'll be asked for one each time you sign in." },
];

/**
 * Two-step sign-in set up on one page, right after signing in (2026-11-01): what to do on the left, the QR code and
 * the first code on the right. `skip`: where "Skip this" goes; null when it's required. The QR code opens by itself
 * since the password was just given; a page opened later on asks for it first.
 */
export function TwoStepWelcome({ skip, onDone }: { skip: string | null; onDone: () => void }) {
  const [started, setStarted] = useState<TwoStepStart | null>(null);
  const [needsPassword, setNeedsPassword] = useState(false);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string>();
  const [busy, start] = useTransition();

  useEffect(() => {
    let live = true;
    void startTwoStep().then((r) => {
      if (!live) return;
      if (r.ok) setStarted(r.data);
      else setNeedsPassword(true);
    });
    return () => {
      live = false;
    };
  }, []);

  if (codes) {
    return (
      <div className="w-full max-w-[26rem]">
        <h1 className="mb-6 text-center text-[1.75rem] leading-[1.15] font-semibold tracking-[-0.02em] text-ink">Keep your recovery codes</h1>
        <RecoveryCodes codes={codes} onDone={onDone} />
      </div>
    );
  }

  return (
    <div className="w-full max-w-[56rem]">
      <div className="grid gap-x-12 gap-y-10 md:grid-cols-[minmax(0,1fr)_20rem] md:items-center">
        <div>
          <h1 className="text-[2rem] leading-[1.15] font-semibold tracking-[-0.02em] text-ink sm:text-[2.25rem]">Set up two-step sign-in</h1>
          <p className="mt-3 text-sm leading-relaxed text-ink-2">A code from your phone keeps your account safe, even if someone gets your password. It takes a minute.</p>
          <ol className="mt-8 space-y-6">
            {STEPS.map((s) => (
              <li key={s.title} className="flex gap-4">
                <span className="grid size-11 shrink-0 place-items-center rounded-full bg-hema-tint text-sage-deep">{s.icon}</span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-ink">{s.title}</span>
                  <span className="mt-0.5 block text-sm text-ink-2">{s.text}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>

        <div>
          {started ? (
            <form
              className="space-y-4"
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                start(async () => {
                  const r = await confirmTwoStep(code);
                  if (r.ok) setCodes(r.data.recoveryCodes ?? []);
                  else setError(r.error);
                });
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={started.qr} alt="QR code to add Bishnoi One to your authenticator app" className="mx-auto size-52 rounded-lg border border-rule bg-white p-1" />
              <p className="text-center text-meta font-medium text-ink-2">Scan this QR code</p>
              <details className="text-meta text-ink-3">
                <summary className="cursor-pointer text-center">Can&apos;t scan it?</summary>
                <p className="mt-1.5 text-center">
                  Enter this key in the app: <span className="font-mono break-all text-ink">{started.secret.replace(/(.{4})/g, "$1 ").trim()}</span>
                </p>
              </details>
              <Field label="The six digits the app shows">
                {(p) => <Input {...p} inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} maxLength={8} />}
              </Field>
              <FormError message={error} />
              <Button type="submit" variant="primary" size="lg" loading={busy} className="w-full justify-center">
                Turn it on
              </Button>
            </form>
          ) : needsPassword ? (
            <form
              className="space-y-4"
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                start(async () => {
                  const r = await startTwoStep(password);
                  if (r.ok) {
                    setStarted(r.data);
                    setError(undefined);
                  } else setError(r.error);
                });
              }}
            >
              <Field label="Your password">{(p) => <PasswordInput {...p} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" autoFocus />}</Field>
              <FormError message={error} />
              <Button type="submit" variant="primary" size="lg" loading={busy} className="w-full justify-center">
                Show the QR code
              </Button>
            </form>
          ) : (
            <div role="status" aria-label="Loading the QR code" className="mx-auto size-52 animate-pulse rounded-lg bg-bench" />
          )}
          {skip && (
            <a href={skip} className="mt-4 block py-2 text-center text-sm font-medium text-ink-2 underline-offset-2 hover:text-ink hover:underline">
              Skip this
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
