"use client";

import { useActionState } from "react";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { signInAccount, type GoState } from "./actions";

/** The Nabhi account sign-in: email and password, then on to the application. */
export function GoForm({ app, returnTo }: { app: string; returnTo: string }) {
  const [state, action, pending] = useActionState<GoState, FormData>(signInAccount, null);
  return (
    <form action={action} className="mt-6 space-y-5" noValidate>
      <input type="hidden" name="app" value={app} />
      <input type="hidden" name="return" value={returnTo} />
      <Field label="Work email">
        {(p) => <Input {...p} name="email" type="email" autoComplete="username" defaultValue={state?.email ?? ""} autoFocus required />}
      </Field>
      <Field label="Password">
        {(p) => <Input {...p} name="password" type="password" autoComplete="current-password" required />}
      </Field>
      <FormError message={state?.error} />
      <Button type="submit" variant="primary" loading={pending} className="w-full justify-center">
        Sign in
      </Button>
    </form>
  );
}
