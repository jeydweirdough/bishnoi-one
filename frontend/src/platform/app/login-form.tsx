"use client";

import { useActionState, useRef, type ReactNode } from "react";
import { signIn, type SignInState } from "../actions/session";
import { Button } from "../ui/button";
import { Field, FormError, Input } from "../ui/field";

/** `group` heads a run of accounts, so a long list stays scannable. */
export type Demo = { email: string; who: string; role: string; group: string };

/**
 * The sign-in screen: this app's demo accounts on the left (development only),
 * the sign-in card on the right. Picking a demo account fills the form. On a
 * narrow screen the card comes first and the accounts follow it.
 */
export function LoginForm({
  next,
  demo,
  demoPassword,
  children,
}: {
  next: string;
  demo: Demo[];
  demoPassword: string | null;
  children: ReactNode;
}) {
  const [state, action, pending] = useActionState<SignInState, FormData>(signIn, null);
  const email = useRef<HTMLInputElement>(null);
  const password = useRef<HTMLInputElement>(null);

  function fillDemo(address: string) {
    if (email.current) email.current.value = address;
    if (password.current && demoPassword) password.current.value = demoPassword;
    password.current?.focus();
  }

  const card = (
    <div className="rounded-[3px] bg-sheet px-6 pt-6 pb-7 shadow-sheet sm:px-8">
      {children}
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
    </div>
  );

  if (demo.length === 0) return <div className="w-full max-w-[25rem]">{card}</div>;

  return (
    <div className="grid w-full max-w-[56rem] gap-6 md:grid-cols-[minmax(0,1fr)_25rem] md:items-start">
      <div className="md:order-2">{card}</div>
      <aside aria-labelledby="demo-accounts" className="rounded-[3px] border border-rule px-5 py-5 text-meta md:order-1 md:max-h-[calc(100dvh-5rem)] md:overflow-y-auto">
        <h2 id="demo-accounts" className="font-semibold text-ink-2">
          Demo accounts
        </h2>
        <p className="mt-1 text-ink-3">
          Pick one to fill the form{demoPassword ? <>. Password <span className="font-medium text-ink-2">{demoPassword}</span></> : null}.
        </p>
        <ul className="mt-3 divide-y divide-rule">
          {demo.map((d, i) => (
            <li key={d.email}>
              {d.group !== demo[i - 1]?.group && (
                <p className="mt-3 pt-3 text-caps text-ink-3 uppercase first:mt-0 first:pt-0">{d.group}</p>
              )}
              <button type="button" onClick={() => fillDemo(d.email)} className="w-full py-2 text-left hover:text-hema">
                <span className="font-medium">{d.who}</span>
                <span className="block text-ink-3">{d.role}</span>
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
