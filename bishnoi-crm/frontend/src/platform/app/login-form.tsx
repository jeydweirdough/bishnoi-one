"use client";

import { Eye, EyeOff } from "lucide-react";
import { useActionState, useId, useRef, useState } from "react";
import { checkCompany, checkPassword, signIn, type SignInState } from "../actions/session";
import { SignInProgress } from "../screens/sign-in-progress";

/** `group` heads a run of accounts, so a long list stays scannable. */
export type Demo = { email: string; who: string; role: string; group: string };

// The sign-in form's own look (src/components/sign-in/showcase.tsx has the
// picture beside it): rounded fields with a grey outline, a black button.
const FIELD =
  "block h-12 w-full rounded-lg border border-[#8a8a8a] bg-white px-4 text-sm text-[#141414] placeholder:text-[#7a7a7a] transition-colors focus:border-[#141414] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#a8d69b] aria-[invalid=true]:border-danger";

/**
 * Company, work email and password, then Sign in. The company is filled in
 * from the last sign-in on this browser. In development, the demo accounts
 * sit under the form, closed, and picking one fills it.
 */
export function LoginForm({
  next,
  company,
  demo,
  demoPassword,
  bishnoiAccount,
}: {
  next: string;
  /** The company last signed in to on this browser. */
  company: string;
  demo: Demo[];
  demoPassword: string | null;
  /** Where "Sign in with your Bishnoi One account" goes; null when the platform isn't set up. */
  bishnoiAccount: string | null;
}) {
  const [state, action, pending] = useActionState<SignInState, FormData>(signIn, null);
  const password = useRef<HTMLInputElement>(null);
  const ids = { company: useId(), email: useId(), password: useId(), hint: useId(), forgot: useId() };
  const [companyValue, setCompanyValue] = useState(state?.company ?? company);
  const [emailValue, setEmailValue] = useState(state?.email ?? "");
  const [passwordValue, setPasswordValue] = useState("");
  const [shown, setShown] = useState(false);
  const [forgot, setForgot] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  // Signing in, a step at a time, on a screen of its own; back here, with why, if a step fails.
  // Signed in (the credentials checked on the form): then the loading screen, a step at a time.
  const [signing, setSigning] = useState(false);
  const [checking, setChecking] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const error = failed ?? state?.error;

  function fillDemo(address: string) {
    setPicked(address);
    setEmailValue(address);
    if (demoPassword) setPasswordValue(demoPassword);
    password.current?.focus();
  }

  return (
    <div className="w-full">
      {signing && (
        <SignInProgress
          next={next}
          onBack={(why) => {
            setSigning(false);
            setFailed(why);
          }}
        />
      )}
      {/* Without scripts, the form posts as before (signIn); with them, the steps are shown. */}
      <form
        action={action}
        className="space-y-3"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          setFailed(null);
          if (!emailValue.trim() || !passwordValue) return setFailed("Enter your email and password.");
          // The credentials are checked here, on the form: a wrong one is said
          // beside the fields. The loading screen opens only once they're right.
          setChecking(true);
          (async () => {
            const unanswered = "Bishnoi One didn't answer. Check your connection, and try again.";
            const found = await checkCompany(companyValue.trim()).catch(() => ({ ok: false as const, error: unanswered }));
            if (!found.ok) return setFailed(found.error);
            const right = await checkPassword(companyValue.trim(), emailValue.trim(), passwordValue).catch(() => ({ ok: false as const, error: unanswered }));
            if (!right.ok) return setFailed(right.error);
            setSigning(true);
          })().finally(() => setChecking(false));
        }}
      >
        <input type="hidden" name="next" value={next} />
        <div>
          <label htmlFor={ids.company} className="sr-only">
            Company
          </label>
          <input
            id={ids.company}
            name="company"
            className={FIELD}
            placeholder="Company, e.g. getmeds"
            autoComplete="organization"
            autoCapitalize="none"
            spellCheck={false}
            value={companyValue}
            onChange={(e) => setCompanyValue(e.target.value)}
            aria-describedby={ids.hint}
            required
            autoFocus={!companyValue}
          />
          <p id={ids.hint} className="mt-1.5 px-6 text-meta text-[#6a6a6a]">
            Your company&apos;s short name on Bishnoi One.
          </p>
        </div>
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
            autoFocus={!!companyValue}
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
            className="absolute top-1/2 right-4 -translate-y-1/2 rounded-md p-1.5 text-[#6a6a6a] hover:text-[#141414] focus-visible:ring-2 focus-visible:ring-[#a8d69b] focus-visible:outline-none"
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
          <p id={ids.forgot} className="rounded-lg bg-[#f1f7ee] px-5 py-2.5 text-meta text-[#3b3b3b]">
            Passwords are reset by your administrator. Ask them for a new one, then change it from your account page.
          </p>
        )}

        {error && (
          <p role="alert" className="rounded-lg bg-danger-tint px-5 py-2.5 text-sm text-danger">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={pending || checking || signing}
          className="mt-2 flex h-12 w-full items-center justify-center rounded-lg bg-[#141414] text-sm font-medium text-white transition-colors hover:bg-[#2b2b2b] focus-visible:ring-2 focus-visible:ring-[#a8d69b] focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-70"
        >
          {pending || checking || signing ? "Signing in…" : "Sign in"}
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
              className="group flex items-center gap-3 rounded-lg bg-[#141414] py-2 pr-5 pl-2 text-sm font-medium text-white transition-colors hover:bg-[#2b2b2b] focus-visible:ring-2 focus-visible:ring-[#a8d69b] focus-visible:ring-offset-2 focus-visible:outline-none"
            >
              <img src="/brand/bishnoi-one-mark.png" alt="" width={36} height={36} className="size-9 rounded-full bg-white p-0.5" />
              Sign in with Bishnoi One
            </a>
          </div>
        </div>
      )}

      {demo.length > 0 && (
        <details className="mt-8 rounded-xl border border-[#e2e2e2] px-5 py-3 text-meta">
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
                        className={`rounded-md border px-3 py-1 transition-colors ${
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
