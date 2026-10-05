"use client";

import { useActionState, useRef, useState, type ReactNode } from "react";
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
  company,
  demo,
  demoPassword,
  children,
}: {
  next: string;
  /** The company last signed in to on this browser, filled in. */
  company: string;
  demo: Demo[];
  demoPassword: string | null;
  children: ReactNode;
}) {
  const [state, action, pending] = useActionState<SignInState, FormData>(signIn, null);
  const password = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<string | null>(null);
  // The fields hold their values here (Ant's inputs keep their own copy, so
  // writing to the element directly doesn't stick): a demo account fills both.
  const [emailValue, setEmailValue] = useState(state?.email ?? "");
  const [passwordValue, setPasswordValue] = useState("");
  const [companyValue, setCompanyValue] = useState(state?.company ?? company);

  function fillDemo(address: string) {
    setPicked(address);
    setEmailValue(address);
    if (demoPassword) setPasswordValue(demoPassword);
    password.current?.focus();
  }

  const card = (
    <div className="rounded-[6px] bg-sheet px-6 pt-6 pb-7 shadow-sheet sm:px-8">
      {children}
      <form action={action} className="mt-6 space-y-5" noValidate>
        <input type="hidden" name="next" value={next} />
        {/* Each company on Bishnoi One has its own CRM data: which one is
            asked first, by the short name the platform gave it. */}
        <Field label="Company" hint="Your company's short name on Bishnoi One, for example getmeds.">
          {(p) => (
            <Input
              {...p}
              name="company"
              autoComplete="organization"
              autoCapitalize="none"
              spellCheck={false}
              value={companyValue}
              onChange={(e) => setCompanyValue(e.target.value)}
              required
              autoFocus={!companyValue}
            />
          )}
        </Field>
        <Field label="Work email">
          {(p) => (
            <Input
              {...p}
              name="email"
              type="email"
              autoComplete="username"
              inputMode="email"
              value={emailValue}
              onChange={(e) => setEmailValue(e.target.value)}
              required
              autoFocus={!!companyValue}
            />
          )}
        </Field>
        <Field label="Password">
          {(p) => (
            <Input
              {...p}
              ref={password}
              name="password"
              type="password"
              autoComplete="current-password"
              value={passwordValue}
              onChange={(e) => setPasswordValue(e.target.value)}
              required
            />
          )}
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
      <aside aria-labelledby="demo-accounts" className="rounded-[6px] border border-rule px-5 py-5 text-meta md:order-1 md:max-h-[calc(100dvh-5rem)] md:overflow-y-auto">
        <h2 id="demo-accounts" className="font-semibold text-ink-2">
          Demo accounts
        </h2>
        <p className="mt-1 text-ink-3">
          Pick one to fill the form{demoPassword ? <>. Password <span className="font-medium text-ink-2">{demoPassword}</span></> : null}.
        </p>
        <div className="mt-2">
          {groups(demo).map(([group, people]) => (
            <section key={group} className="mt-4 first:mt-3">
              <h3 className="text-caps text-ink-3 uppercase">{group}</h3>
              <ul className="mt-2 flex flex-wrap gap-2">
                {people.map((d) => (
                  <li key={d.email}>
                    <button
                      type="button"
                      onClick={() => fillDemo(d.email)}
                      title={`${d.role} — ${d.email}`}
                      aria-pressed={picked === d.email}
                      className={`rounded-full border px-3 py-1 transition-colors ${
                        picked === d.email
                          ? "border-hema bg-hema-tint text-ink"
                          : "border-rule-strong bg-sheet text-ink hover:border-hema hover:text-ink"
                      }`}
                    >
                      <span className="font-medium">{d.who}</span>
                      <span className="text-ink-3"> · {shortRole(d.role)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </aside>
    </div>
  );
}

/** Accounts under their group headings, in the order they came. */
function groups(demo: Demo[]): [string, Demo[]][] {
  const byGroup = new Map<string, Demo[]>();
  for (const d of demo) byGroup.set(d.group, [...(byGroup.get(d.group) ?? []), d]);
  return [...byGroup];
}

/** "Rep · B2C MD Telesales" -> "Rep": the chip says what they are; hovering says the rest. */
function shortRole(role: string): string {
  return role.split("·")[0].trim();
}
