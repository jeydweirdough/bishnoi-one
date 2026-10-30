"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { Button } from "@/src/platform/ui/ant-button";
import { Field, FormError, Input, PasswordInput } from "@/src/platform/ui/field";
import { changePassword, confirmTwoStep, forgotPassword, setPasswordByLink, startTwoStep, type TwoStepStart } from "./actions";

// The sign-in pages' forms (2026-10-30): forgot password, a reset or invitation link's new password,
// the first sign-in's own password, and setting up two-step sign-in.

const HINT = "At least 8 characters, not your name or email. A short phrase is easiest to remember.";

/** Forgot password: the email, then the same answer whatever it is (nobody learns which emails have accounts). */
export function ForgotForm({ email: first }: { email: string }) {
  const [email, setEmail] = useState(first);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string>();
  const [busy, start] = useTransition();
  if (sent) {
    return (
      <div className="mt-8 space-y-4 text-center text-sm text-ink-2">
        <p>
          If <strong className="text-ink">{email}</strong> has a Bishnoi One account, a link to choose a new password is on its way. It works for an hour.
        </p>
        <p className="text-meta text-ink-3">Nothing after a few minutes? Check spam, or ask your company&apos;s administrator for a sign-in link.</p>
        <Link href="/login" className="inline-block text-hema hover:underline">
          Back to sign in
        </Link>
      </div>
    );
  }
  return (
    <form
      className="mt-8 space-y-5"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (!email.trim()) return setError("Enter your work email.");
        start(async () => {
          const r = await forgotPassword(email);
          if (r.ok) setSent(true);
          else setError(r.error);
        });
      }}
    >
      <Field label="Work email">{(p) => <Input {...p} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />}</Field>
      <FormError message={error} />
      <Button type="submit" variant="primary" size="lg" loading={busy} className="w-full justify-center">
        Send me a link
      </Button>
      <p className="text-center">
        <Link href="/login" className="text-meta text-ink-2 hover:text-hema hover:underline">
          Back to sign in
        </Link>
      </p>
    </form>
  );
}

/** A new password, typed twice. `save` sends it; then `done` shows. */
function NewPassword({ save, label, done }: { save: (password: string) => Promise<{ ok: boolean; error?: string }>; label: string; done: () => void }) {
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string>();
  const [busy, start] = useTransition();
  return (
    <form
      className="mt-8 space-y-5"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (password.length < 8) return setError("Use at least 8 characters.");
        if (password !== again) return setError("The two passwords aren't the same.");
        start(async () => {
          const r = await save(password);
          if (r.ok) done();
          else setError(r.error);
        });
      }}
    >
      <Field label="New password" hint={HINT}>
        {(p) => <PasswordInput {...p} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" autoFocus />}
      </Field>
      <Field label="The same again">{(p) => <PasswordInput {...p} value={again} onChange={(e) => setAgain(e.target.value)} autoComplete="new-password" />}</Field>
      <FormError message={error} />
      <Button type="submit" variant="primary" size="lg" loading={busy} className="w-full justify-center">
        {label}
      </Button>
    </form>
  );
}

/** A reset or invitation link: their own password, then sign in with it. */
export function LinkPasswordForm({ token, email, invite }: { token: string; email: string; invite: boolean }) {
  const [done, setDone] = useState(false);
  if (done) {
    return (
      <div className="mt-8 space-y-4 text-center text-sm text-ink-2">
        <p>Your password is set. Sign in with {email} and your new password.</p>
        <Button variant="primary" size="lg" className="w-full justify-center" onClick={() => window.location.assign(`/login?email=${encodeURIComponent(email)}`)}>
          Sign in
        </Button>
      </div>
    );
  }
  return <NewPassword save={(p) => setPasswordByLink(token, p)} label={invite ? "Set my password" : "Save my new password"} done={() => setDone(true)} />;
}

/** The first sign-in with a password someone handed over: their own, typed with the one they were given. */
export function FirstPasswordForm({ onDone }: { onDone: () => void }) {
  const [given, setGiven] = useState("");
  const [error, setError] = useState<string>();
  return (
    <>
      <div className="mt-8">
        <Field label="The password you were given">
          {(p) => <PasswordInput {...p} value={given} onChange={(e) => (setGiven(e.target.value), setError(undefined))} autoComplete="current-password" autoFocus />}
        </Field>
      </div>
      <FormError message={error} />
      <NewPassword
        label="Save my password"
        save={async (p) => {
          if (!given) return { ok: false, error: "Enter the password you were given first." };
          const r = await changePassword(given, p);
          return r.ok ? { ok: true } : { ok: false, error: r.error };
        }}
        done={onDone}
      />
    </>
  );
}

/** Two-step sign-in: password, then scan the code, then the first six digits; the recovery codes shown once. */
export function TwoStepSetup({ onDone, compact = false }: { onDone: () => void; compact?: boolean }) {
  const [password, setPassword] = useState("");
  const [started, setStarted] = useState<TwoStepStart | null>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string>();
  const [busy, start] = useTransition();

  if (codes) {
    return (
      <div className={`${compact ? "" : "mt-8 "}space-y-4`}>
        <p className="text-sm text-ink-2">
          Two-step sign-in is on. Keep these recovery codes somewhere safe (printed, or in a password manager). Each one signs you in once if you lose your phone.
          They won&apos;t be shown again.
        </p>
        <ul className="grid grid-cols-2 gap-2 rounded-lg border border-rule bg-bench p-3 font-mono text-sm text-ink">
          {codes.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
        <div className="flex gap-2">
          <Button onClick={() => void navigator.clipboard?.writeText(codes.join("\n"))}>Copy codes</Button>
          <Button variant="primary" className="flex-1 justify-center" onClick={onDone}>
            I&apos;ve kept them
          </Button>
        </div>
      </div>
    );
  }

  if (!started) {
    return (
      <form
        className={`${compact ? "" : "mt-8 "}space-y-5`}
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          start(async () => {
            const r = await startTwoStep(password);
            if (r.ok) (setStarted(r.data), setError(undefined));
            else setError(r.error);
          });
        }}
      >
        <p className="text-sm text-ink-2">
          You&apos;ll need an authenticator app on your phone: Google Authenticator, Microsoft Authenticator or 1Password. Then each sign-in asks for the six digits it shows.
        </p>
        <Field label="Your password">{(p) => <PasswordInput {...p} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" autoFocus={!compact} />}</Field>
        <FormError message={error} />
        <Button type="submit" variant="primary" loading={busy} className={compact ? "" : "w-full justify-center"} size={compact ? "md" : "lg"}>
          Set up two-step sign-in
        </Button>
      </form>
    );
  }

  return (
    <form
      className={`${compact ? "" : "mt-8 "}space-y-4`}
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
      <p className="text-sm text-ink-2">1. In the app, add an account and scan this code.</p>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={started.qr} alt="QR code to add Bishnoi One to your authenticator app" className="mx-auto size-48 rounded-lg border border-rule bg-white p-1" />
      <p className="text-meta text-ink-3">
        Can&apos;t scan? Enter this key in the app instead: <span className="font-mono break-all text-ink">{started.secret.replace(/(.{4})/g, "$1 ").trim()}</span>
      </p>
      <Field label="2. The six digits the app shows">
        {(p) => <Input {...p} inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} maxLength={8} autoFocus />}
      </Field>
      <FormError message={error} />
      <Button type="submit" variant="primary" loading={busy} className={compact ? "" : "w-full justify-center"} size={compact ? "md" : "lg"}>
        Turn it on
      </Button>
    </form>
  );
}
