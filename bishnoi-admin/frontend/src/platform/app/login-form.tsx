"use client";

import { Eye, EyeOff } from "lucide-react";
import { useActionState, useId, useRef, useState } from "react";
import { signIn, type SignInState } from "../actions/session";

/** `group` heads a run of accounts, so a long list stays scannable. */
export type Demo = { email: string; who: string; role: string; group: string };

// The sign-in form's own look (src/components/sign-in/showcase.tsx has the
// picture beside it): rounded fields with a grey outline, a black button.
const FIELD =
  "block h-12 w-full rounded-full border border-[#8a8a8a] bg-white px-6 text-sm text-[#141414] placeholder:text-[#7a7a7a] transition-colors focus:border-[#141414] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#a8d69b] aria-[invalid=true]:border-danger";

/**
 * Work email and password, then Sign in (the CRM's form, without the company:
 * Executive Admin keeps one company's records). In development, the demo accounts
 * sit under the form, closed, and picking one fills it.
 */
export function LoginForm({
  next,
  demo,
  demoPassword,
  bishnoiAccount,
}: {
  next: string;
  demo: Demo[];
  demoPassword: string | null;
  /** Where "Sign in with your Bishnoi One account" goes; null when the platform isn't set up. */
  bishnoiAccount: string | null;
}) {
  const [state, action, pending] = useActionState<SignInState, FormData>(signIn, null);
  const password = useRef<HTMLInputElement>(null);
  const ids = { email: useId(), password: useId(), forgot: useId() };
  const [emailValue, setEmailValue] = useState(state?.email ?? "");
  const [passwordValue, setPasswordValue] = useState("");
  const [shown, setShown] = useState(false);
  const [forgot, setForgot] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);

  function fillDemo(address: string) {
    setPicked(address);
    setEmailValue(address);
    if (demoPassword) setPasswordValue(demoPassword);
    password.current?.focus();
  }

  return (
    <div className="w-full">
      <form action={action} className="space-y-3" noValidate>
        <input type="hidden" name="next" value={next} />
        <div>
          <label htmlFor={ids.email} className="sr-only">
            Work email
          </label>
          <input
            id={ids.email}
            name="email"
            type="email"
            className={FIELD}
            placeholder="Work email"
            autoComplete="username"
            inputMode="email"
            value={emailValue}
            onChange={(e) => setEmailValue(e.target.value)}
            required
            autoFocus
          />
        </div>
        <div className="relative">
          <label htmlFor={ids.password} className="sr-only">
            Password
          </label>
          <input
            id={ids.password}
            ref={password}
            name="password"
            type={shown ? "text" : "password"}
            className={`${FIELD} pr-14`}
            placeholder="Password"
            autoComplete="current-password"
            value={passwordValue}
            onChange={(e) => setPasswordValue(e.target.value)}
            required
          />
          <button
            type="button"
            onClick={() => setShown((s) => !s)}
            aria-label={shown ? "Hide password" : "Show password"}
            aria-pressed={shown}
            className="absolute top-1/2 right-4 -translate-y-1/2 rounded-full p-1.5 text-[#6a6a6a] hover:text-[#141414] focus-visible:ring-2 focus-visible:ring-[#a8d69b] focus-visible:outline-none"
          >
            {shown ? <EyeOff className="size-[18px]" aria-hidden /> : <Eye className="size-[18px]" aria-hidden />}
          </button>
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setForgot((f) => !f)}
            aria-expanded={forgot}
            aria-controls={ids.forgot}
            className="text-meta font-medium text-[#141414] hover:underline focus-visible:underline focus-visible:outline-none"
          >
            Forgot password?
          </button>
        </div>
        {forgot && (
          <p id={ids.forgot} className="rounded-2xl bg-[#f1f7ee] px-5 py-2.5 text-meta text-[#3b3b3b]">
            Passwords are reset by your administrator. Ask them for a new one, then change it from your account page.
          </p>
        )}

        {state?.error && (
          <p role="alert" className="rounded-2xl bg-danger-tint px-5 py-2.5 text-sm text-danger">
            {state.error}
          </p>
        )}

        <button
          type="submit"
          disabled={pending}
          className="mt-2 flex h-12 w-full items-center justify-center rounded-full bg-[#141414] text-sm font-medium text-white transition-colors hover:bg-[#2b2b2b] focus-visible:ring-2 focus-visible:ring-[#a8d69b] focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-70"
        >
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {bishnoiAccount && (
        <div className="mt-8">
          <p className="flex items-center gap-4 text-sm text-[#3b3b3b]">
            <span className="h-px flex-1 bg-[#d6d6d6]" aria-hidden />
            or continue with
            <span className="h-px flex-1 bg-[#d6d6d6]" aria-hidden />
          </p>
          <div className="mt-5 flex justify-center">
            <a
              href={bishnoiAccount}
              className="group flex items-center gap-3 rounded-full bg-[#141414] py-2 pr-5 pl-2 text-sm font-medium text-white transition-colors hover:bg-[#2b2b2b] focus-visible:ring-2 focus-visible:ring-[#a8d69b] focus-visible:ring-offset-2 focus-visible:outline-none"
            >
              <img src="/brand/bishnoi-one-mark.png" alt="" width={36} height={36} className="size-9 rounded-full bg-white p-0.5" />
              Your Bishnoi One account
            </a>
          </div>
        </div>
      )}

      {demo.length > 0 && (
        <details className="mt-8 rounded-2xl border border-[#e2e2e2] px-5 py-3 text-meta">
          <summary className="cursor-pointer font-medium text-[#3b3b3b]">
            Demo accounts (this computer only){demoPassword ? ` · password ${demoPassword}` : ""}
          </summary>
          <div className="mt-2 max-h-64 overflow-y-auto">
            {groups(demo).map(([group, people]) => (
              <section key={group} className="mt-3">
                <h3 className="text-caps text-[#6a6a6a] uppercase">{group}</h3>
                <ul className="mt-1.5 flex flex-wrap gap-1.5">
                  {people.map((d) => (
                    <li key={d.email}>
                      <button
                        type="button"
                        onClick={() => fillDemo(d.email)}
                        title={`${d.role} — ${d.email}`}
                        aria-pressed={picked === d.email}
                        className={`rounded-full border px-3 py-1 transition-colors ${
                          picked === d.email ? "border-[#5e8f52] bg-[#f1f7ee] text-[#141414]" : "border-[#cfcfcf] bg-white text-[#141414] hover:border-[#5e8f52]"
                        }`}
                      >
                        <span className="font-medium">{d.who}</span>
                        <span className="text-[#6a6a6a]"> · {shortRole(d.role)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </details>
      )}
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
