"use client";

import Link from "next/link";
import { useActionState, useEffect, useState } from "react";
import { Button } from "@/src/platform/ui/ant-button";
import { Field, FormError, Input, PasswordInput } from "@/src/platform/ui/field";
import { signIn, signInCode, type SignInState } from "./actions";

/** The Bishnoi One sign-in: email and password, then (with two-step sign-in on) the code, then into the one app. */
export function LoginForm({ next, email: given = "" }: { next: string; email?: string }) {
  const [state, action, pending] = useActionState<SignInState, FormData>(signIn, null);
  // Kept as typed, so a wrong try leaves both there to fix.
  const [email, setEmail] = useState(given);
  const [password, setPassword] = useState("");
  // Signed in: the browser goes on, so a module's session can be opened on the way (see signIn).
  useEffect(() => {
    if (state?.go) window.location.assign(state.go);
  }, [state?.go]);
  if (state?.ticket) return <CodeForm ticket={state.ticket} email={state.email ?? email} next={next} />;
  return (
    <form action={action} className="mt-8 space-y-5" noValidate>
      <input suppressHydrationWarning type="hidden" name="next" value={next} />
      <Field label="Work email">
        {(p) => <Input {...p} name="email" type="email" autoComplete="username" value={email || state?.email || ""} onChange={(e) => setEmail(e.target.value)} autoFocus required />}
      </Field>
      <Field label="Password">
        {(p) => <PasswordInput {...p} name="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />}
      </Field>
      <div className="-mt-2 text-right">
        <Link href={`/login/forgot${email ? `?email=${encodeURIComponent(email)}` : ""}`} className="text-meta text-ink-2 hover:text-hema hover:underline">
          Forgot your password?
        </Link>
      </div>
      <FormError message={state?.error} />
      <Button type="submit" variant="primary" size="lg" loading={pending || Boolean(state?.go)} className="w-full justify-center">
        Sign in
      </Button>
    </form>
  );
}

/** The second step: the six digits the authenticator app shows now, or a recovery code. */
function CodeForm({ ticket, email, next }: { ticket: string; email: string; next: string }) {
  const [state, action, pending] = useActionState<SignInState, FormData>(signInCode, { ticket, email });
  const [code, setCode] = useState("");
  useEffect(() => {
    if (state?.go) window.location.assign(state.go);
  }, [state?.go]);
  // The ticket ran out (five minutes): start again with the password.
  if (!state?.ticket && !state?.go) {
    return (
      <div className="mt-8 space-y-4 text-center">
        <FormError message={state?.error ?? "This sign-in took too long."} />
        <Button variant="primary" size="lg" className="w-full justify-center" onClick={() => window.location.reload()}>
          Sign in again
        </Button>
      </div>
    );
  }
  return (
    <form action={action} className="mt-8 space-y-5" noValidate>
      <input type="hidden" name="ticket" value={state.ticket ?? ticket} />
      <input type="hidden" name="email" value={email} />
      <input type="hidden" name="next" value={next} />
      <p className="text-sm text-ink-2">
        Open your authenticator app and enter the code for <strong className="text-ink">{email}</strong>.
      </p>
      <Field label="Code" hint="Six digits. Lost your phone? Enter one of your recovery codes instead.">
        {(p) => (
          <Input
            {...p}
            name="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            maxLength={20}
            autoFocus
            required
          />
        )}
      </Field>
      <FormError message={state?.error} />
      <Button type="submit" variant="primary" size="lg" loading={pending || Boolean(state?.go)} className="w-full justify-center">
        Continue
      </Button>
    </form>
  );
}
