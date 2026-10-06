"use client";

import { Eye, EyeOff } from "lucide-react";
import { useActionState, useId, useRef, useState, type ReactNode } from "react";
import { signIn, type SignInState } from "../actions/session";
import { Spinner } from "../ui/button";

/** `group` heads a run of accounts, so a long list stays scannable. */
export type Demo = { email: string; who: string; role: string; group: string };

// Underlined fields, as on the sign-in design: no box, a rule beneath that
// turns blue while typing in it.
// GetMEDS blue (#1d9fda) from a lighter blue at the top left to navy at the bottom right.
const PANEL = "linear-gradient(150deg, #5cc3ee 0%, #1d9fda 40%, #1379b8 70%, #0c4f8c 100%)";

const line =
  "block h-10 w-full min-w-0 border-0 border-b border-rule-strong bg-transparent px-0 text-sm text-ink placeholder:text-ink-3/70 focus:border-section focus:outline-none aria-[invalid=true]:border-danger";

/**
 * The sign-in screen: the blue panel (its contents in `panel`) and the form
 * beside it. In development this app's demo accounts follow the form, and
 * picking one fills it. On a phone the panel is hidden and `brand` heads the
 * form instead.
 */
export function LoginForm({
  next,
  demo,
  demoPassword,
  notice,
  before,
  brand,
  panel,
}: {
  next: string;
  demo: Demo[];
  demoPassword: string | null;
  notice?: ReactNode;
  /** Above the email field: a refused sign-in from the platform, and the other way in. */
  before?: ReactNode;
  brand: ReactNode;
  panel: ReactNode;
}) {
  const [state, action, pending] = useActionState<SignInState, FormData>(signIn, null);
  const email = useRef<HTMLInputElement>(null);
  const password = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [shown, setShown] = useState(false);
  const id = useId();

  function fillDemo(address: string) {
    setPicked(address);
    if (email.current) email.current.value = address;
    if (password.current && demoPassword) password.current.value = demoPassword;
    password.current?.focus();
  }

  const form = (
    <div className="mx-auto w-full max-w-[26rem]">
      {/* The panel is hidden on a narrow screen, so the logo and name come here instead. */}
      <div className="mb-10 lg:hidden">{brand}</div>
      <h1 className="text-[2rem] leading-tight font-bold tracking-tight text-[#0c3a68]">Log in</h1>
      {notice && <p className="mt-2 text-meta text-ink-2">{notice}</p>}
      {before}

      <form action={action} className="mt-8 space-y-6" noValidate>
        <input type="hidden" name="next" value={next} />
        <div>
          <label htmlFor={`${id}-email`} className="block text-meta text-ink-3">
            Email
          </label>
          <input
            id={`${id}-email`}
            ref={email}
            name="email"
            type="email"
            autoComplete="username"
            inputMode="email"
            defaultValue={state?.email}
            aria-invalid={state?.error ? true : undefined}
            required
            autoFocus
            className={line}
          />
        </div>
        <div>
          <label htmlFor={`${id}-password`} className="block text-meta text-ink-3">
            Password
          </label>
          <div className="relative">
            <input
              id={`${id}-password`}
              ref={password}
              name="password"
              type={shown ? "text" : "password"}
              autoComplete="current-password"
              aria-invalid={state?.error ? true : undefined}
              required
              className={`${line} pr-9`}
            />
            <button
              type="button"
              onClick={() => setShown(!shown)}
              aria-label={shown ? "Hide password" : "Show password"}
              aria-pressed={shown}
              className="absolute inset-y-0 right-0 flex w-9 items-center justify-end text-[#0c3a68] hover:text-section"
            >
              {shown ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
            </button>
          </div>
        </div>

        {state?.error && (
          <p role="alert" className="text-meta text-danger">
            {state.error}
          </p>
        )}

        <button
          type="submit"
          disabled={pending}
          className="flex h-10 w-full max-w-[14rem] items-center justify-center gap-2 rounded-full bg-section text-sm font-semibold text-white transition-colors hover:bg-section-hover disabled:opacity-70"
        >
          {pending && <Spinner />}
          {pending ? "Logging in…" : "Log in"}
        </button>
      </form>

      <p className="mt-5 text-[0.75rem] text-ink-3">
        Forgot password? <span className="font-medium text-section">Ask your administrator to reset it.</span>
      </p>

      {demo.length > 0 && (
        <section aria-labelledby={`${id}-demo`} className="mt-10 border-t border-rule pt-6">
          <h2 id={`${id}-demo`} className="text-meta font-semibold text-ink">
            Use a demo account
          </h2>
          <p className="mt-0.5 text-[0.6875rem] text-ink-3">
            Picking one fills the form
            {demoPassword ? (
              <>
                . Password <span className="font-semibold text-ink-2">{demoPassword}</span>
              </>
            ) : null}
            .
          </p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {demo.map((d) => {
              const on = picked === d.email;
              return (
                <li key={d.email}>
                  <button
                    type="button"
                    onClick={() => fillDemo(d.email)}
                    title={`${d.role} — ${d.email}`}
                    aria-pressed={on}
                    className={`rounded-full border px-3 py-1.5 text-meta transition-colors ${
                      on ? "border-section bg-section/10 text-ink" : "border-rule bg-sheet text-ink hover:border-section"
                    }`}
                  >
                    <span className="font-semibold">{d.who}</span>
                    <span className="text-ink-3"> · {shortRole(d.role)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );

  return (
    <div className="grid min-h-dvh w-full lg:grid-cols-2">
      <section
        aria-label="About this app"
        style={{ background: PANEL }}
        className="relative hidden items-center justify-center overflow-hidden p-10 lg:flex"
      >
        {panel}
      </section>
      <div className="flex flex-col justify-center px-5 py-12 sm:px-8">{form}</div>
    </div>
  );
}

/** "Rep · B2C MD Telesales" -> "Rep": the chip says what they are; hovering says the rest. */
function shortRole(role: string): string {
  return role.split("·")[0].trim();
}
