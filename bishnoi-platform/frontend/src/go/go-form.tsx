"use client";

import { useActionState, useState } from "react";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, PasswordInput } from "@/src/platform/ui/field";
import { signInAccount, type GoState } from "./actions";

/** The Bishnoi One account sign-in: email and password, then on to the application. */
export function GoForm({ app, returnTo, company }: { app: string; returnTo: string; company: string }) {
  const [state, action, pending] = useActionState<GoState, FormData>(signInAccount, null);
  // Kept as typed, so a wrong try leaves both there to fix.
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  return (
    <form action={action} className="mt-8 space-y-5" noValidate>
      <input type="hidden" name="app" value={app} />
      <input type="hidden" name="return" value={returnTo} />
      <input type="hidden" name="company" value={company} />
      <Field label="Work email">
        {(p) => <Input {...p} name="email" type="email" autoComplete="username" value={email || state?.email || ""} onChange={(e) => setEmail(e.target.value)} autoFocus required />}
      </Field>
      <Field label="Password">
        {(p) => <PasswordInput {...p} name="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />}
      </Field>
      <FormError message={state?.error} />
      <Button type="submit" variant="primary" loading={pending} className="w-full justify-center">
        Sign in
      </Button>
    </form>
  );
}
