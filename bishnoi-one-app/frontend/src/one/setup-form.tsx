"use client";

import { useActionState, useEffect } from "react";
import { Button } from "@/src/platform/ui/ant-button";
import { Field, FormError, Input, PasswordInput } from "@/src/platform/ui/field";
import { setUp, type SetUpState } from "./actions";

/** The first run: the setup code, the company, and its first administrator. */
export function SetupForm() {
  const [state, action, pending] = useActionState<SetUpState, FormData>(setUp, null);
  useEffect(() => {
    if (state?.go) window.location.assign(state.go);
  }, [state?.go]);
  const v = state?.values ?? {};
  const err = state?.fields ?? {};
  return (
    <form action={action} className="mt-8 space-y-5" noValidate>
      <Field label="Setup code" hint="Shown in the Platform server's log when it starts, like ABCD-EFGH-JKLM." error={err.code}>
        {(p) => <Input {...p} name="code" defaultValue={v.code} autoComplete="off" autoFocus required />}
      </Field>
      <Field label="Company name" error={err.companyName}>
        {(p) => <Input {...p} name="companyName" defaultValue={v.companyName} autoComplete="organization" required />}
      </Field>
      <Field label="Your name" error={err.name}>
        {(p) => <Input {...p} name="name" defaultValue={v.name} autoComplete="name" required />}
      </Field>
      <Field label="Work email" error={err.email}>
        {(p) => <Input {...p} name="email" type="email" defaultValue={v.email} autoComplete="username" required />}
      </Field>
      <Field label="Password" error={err.password}>
        {(p) => <PasswordInput {...p} name="password" autoComplete="new-password" required />}
      </Field>
      <FormError message={state?.error} />
      <Button type="submit" variant="primary" size="lg" loading={pending || Boolean(state?.go)} className="w-full justify-center">
        Set up
      </Button>
    </form>
  );
}
