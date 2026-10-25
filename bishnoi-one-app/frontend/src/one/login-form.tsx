"use client";

import { useActionState, useEffect, useState } from "react";
import { Button } from "@/src/platform/ui/ant-button";
import { Field, FormError, Input, PasswordInput } from "@/src/platform/ui/field";
import { signIn, type SignInState } from "./actions";

/** The Bishnoi One sign-in: email and password, then into the one app. */
export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState<SignInState, FormData>(signIn, null);
  // Kept as typed, so a wrong try leaves both there to fix.
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // Signed in: the browser goes on, so a module's session can be opened on the way (see signIn).
  useEffect(() => {
    if (state?.go) window.location.assign(state.go);
  }, [state?.go]);
  return (
    <form action={action} className="mt-8 space-y-5" noValidate>
      <input suppressHydrationWarning type="hidden" name="next" value={next} />
      <Field label="Work email">
        {(p) => <Input {...p} name="email" type="email" autoComplete="username" value={email || state?.email || ""} onChange={(e) => setEmail(e.target.value)} autoFocus required />}
      </Field>
      <Field label="Password">
        {(p) => <PasswordInput {...p} name="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />}
      </Field>
      <FormError message={state?.error} />
      <Button type="submit" variant="primary" size="lg" loading={pending || Boolean(state?.go)} className="w-full justify-center">
        Sign in
      </Button>
    </form>
  );
}
