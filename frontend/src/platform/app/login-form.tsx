"use client";

import { useActionState, useRef } from "react";
import { signIn, type SignInState } from "../actions/session";
import { Button } from "../ui/button";
import { Field, FormError, Input } from "../ui/field";

/** `group` heads a run of accounts, so twenty-seven of them stay scannable. */
type Demo = { email: string; who: string; role: string; group?: string };

export function LoginForm({ next, demo }: { next: string; demo: Demo[] }) {
  const [state, action, pending] = useActionState<SignInState, FormData>(signIn, null);
  const email = useRef<HTMLInputElement>(null);
  const password = useRef<HTMLInputElement>(null);

  function fillDemo(address: string) {
    if (email.current) email.current.value = address;
    if (password.current) password.current.value = "demo1234";
    password.current?.focus();
  }

  return (
    <>
      <form action={action} className="mt-6 space-y-5" noValidate>
        <input type="hidden" name="next" value={next} />
        <Field label="Work email">
          {(p) => (
            <Input
              {...p}
              ref={email}
              name="email"
              type="email"
              autoComplete="username"
              inputMode="email"
              defaultValue={state?.email}
              required
              autoFocus
            />
          )}
        </Field>
        <Field label="Password">
          {(p) => <Input {...p} ref={password} name="password" type="password" autoComplete="current-password" required />}
        </Field>
        <FormError message={state?.error} />
        <Button type="submit" variant="primary" loading={pending} className="w-full">
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      {demo.length > 0 && (
        <details className="mt-7 border-t border-rule pt-4 text-meta">
          <summary className="cursor-pointer font-semibold text-ink-2">Demo accounts (password demo1234)</summary>
          <ul className="mt-2 divide-y divide-rule">
            {demo.map((d) => (
              <li key={d.email}>
                {d.group && (
                  <p className="mt-3 border-t border-rule pt-3 text-caps text-ink-3 uppercase first:mt-0 first:border-0 first:pt-0">
                    {d.group}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => fillDemo(d.email)}
                  className="w-full py-2 text-left hover:text-hema"
                >
                  <span className="font-medium">{d.who}</span>
                  <span className="block text-ink-3">{d.role}</span>
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}
