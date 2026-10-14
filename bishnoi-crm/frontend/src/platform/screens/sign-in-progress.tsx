"use client";

import { X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { checkAccess, checkCompany, checkPassword } from "../actions/session";
import { thisAppLabel } from "../lib/apps";

// Signing in, shown as one calm "Please wait a moment" screen. Underneath, each
// step is still a real call, done when that call comes back, never on a timer;
// the line under the title names the step under way, says why when it's slower
// than usual, and a step that fails says why and offers the form again.
//
// The same file is in every app's shared kit (src/platform/screens/sign-in-progress.tsx).

type State = "waiting" | "doing" | "done" | "failed";
type Row = { key: string; title: string; detail: string; working: string; state: State; took?: number };

const SLOW_AFTER = 8; // seconds: then it says why it may be slow

export function SignInProgress({ company, email, password, next, onBack }: { company: string; email: string; password: string; next: string; onBack: (error: string) => void }) {
  const router = useRouter();
  const app = thisAppLabel() ?? "Bishnoi One";
  const [rows, setRows] = useState<Row[]>([
    { key: "company", title: "Your company on Bishnoi One Platform", detail: `Checking that ${company || "your company"} is registered, active, and has ${app}.`, working: `Finding ${company || "your company"} on Bishnoi One Platform…`, state: "waiting" },
    { key: "password", title: "Your email and password", detail: `Checking them, and opening your session.`, working: "Checking your email and password…", state: "waiting" },
    { key: "access", title: "What you can reach", detail: "Reading your role, and which Bishnoi One apps are yours.", working: "Reading your role and your apps…", state: "waiting" },
    { key: "assets", title: "Fonts and pictures", detail: "Loading what the app is drawn with.", working: "Loading fonts and pictures…", state: "waiting" },
    { key: "workspace", title: "Your workspace", detail: "Your menu, and your first page.", working: "Opening your workspace…", state: "waiting" },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const startedAt = useRef<number>(Date.now());
  const ran = useRef(false);

  const set = (key: string, change: Partial<Row>) => setRows((all) => all.map((r) => (r.key === key ? { ...r, ...change } : r)));
  // A tick, so the step under way can say how long it has taken.
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (ran.current) return; // once, even when React runs effects twice in development
    ran.current = true;
    // Done: { data }. Failed: undefined (the screen already says why).
    async function step<T>(key: string, run: () => Promise<{ ok: true; data: T } | { ok: false; error: string }>, done?: (data: T) => string): Promise<{ data: T } | undefined> {
      startedAt.current = Date.now();
      set(key, { state: "doing" });
      const r = await run().catch(() => ({ ok: false as const, error: "Bishnoi One didn't answer. Check your connection, and try again." }));
      const took = (Date.now() - startedAt.current) / 1000;
      if (!r.ok) {
        set(key, { state: "failed", detail: r.error, took });
        setError(r.error);
        return undefined;
      }
      set(key, { state: "done", took, ...(done ? { detail: done(r.data) } : {}) });
      return { data: r.data };
    }
    (async () => {
      const found = await step("company", () => checkCompany(company), (d) => `${d.name} is registered and has ${app}.`);
      if (!found) return;
      if (!(await step("password", () => checkPassword(company, email, password), () => "Right. Your session is open."))) return;
      const access = await step("access", () => checkAccess(next), (d) => (d.elsewhere ? "This app isn't yours: opening the one that is." : `You can use ${app}.`));
      if (!access) return;
      const where = access.data;
      // Real waits: the fonts in use, and the logo, loaded in this browser.
      await step("assets", async () => {
        const logo = new Image();
        logo.src = "/brand/bishnoi-one-mark.png";
        await Promise.all([document.fonts.ready, logo.decode().catch(() => undefined)]);
        return { ok: true as const, data: null };
      }, () => "Loaded.");
      startedAt.current = Date.now();
      set("workspace", { state: "doing", detail: "Your menu, and your first page: this screen gives way to it when it's ready." });
      // Done when the page appears: this screen goes away with it.
      if (where.elsewhere) window.location.assign(where.go);
      else {
        router.replace(where.go);
        router.refresh();
      }
    })();
  }, [app, company, email, next, password, router]);

  const doing = rows.find((r) => r.state === "doing");
  const elapsed = doing ? Math.max(0, Math.floor((now - startedAt.current) / 1000)) : 0;
  const step = doing ? rows.indexOf(doing) + 1 : Math.max(1, rows.filter((r) => r.state === "done").length);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="signing-in"
      className="fixed inset-0 z-50 flex items-center justify-center bg-gradient-to-b from-sheet via-sheet to-hema-tint px-4"
    >
      <div className="flex w-full max-w-sm flex-col items-center text-center">
        {/* A soft halo, a turning arc, and the mark in the middle. */}
        <div className="relative grid size-40 place-items-center rounded-full bg-hema-tint/60 ring-1 ring-sage/30" aria-hidden>
          <div className="absolute inset-3 rounded-full bg-sheet/70 ring-1 ring-sage/25" />
          {!error && (
            <svg viewBox="0 0 100 100" className="absolute inset-0 size-full animate-spin [animation-duration:1.4s]">
              <circle cx="50" cy="50" r="46" fill="none" stroke="var(--color-sage-deep)" strokeWidth="2.5" strokeLinecap="round" strokeDasharray="60 229" />
            </svg>
          )}
          <span className={`relative grid size-20 place-items-center rounded-full shadow-sheet ${error ? "bg-danger" : "bg-sage-deep"}`}>
            {error ? (
              <X className="size-8 text-white" strokeWidth={2.5} />
            ) : (
              <img src="/brand/bishnoi-one-mark.png" alt="" width={40} height={40} className="size-10 brightness-0 invert" />
            )}
          </span>
        </div>

        <h1 id="signing-in" className="mt-10 text-2xl font-semibold text-ink">
          {error ? "Couldn't sign you in" : "Please wait a moment"}
        </h1>
        <p className="mt-2 text-sm text-ink-2" aria-live="polite">
          {error ?? doing?.working ?? `Signing you in to Bishnoi One ${app}…`}
        </p>
        {!error && (
          <p className="mt-3 text-meta text-ink-3 tabular-nums">
            Step {step} of {rows.length}
            {elapsed > 0 && ` · ${elapsed}s`}
          </p>
        )}
        {doing && elapsed >= SLOW_AFTER && (
          <p className="mt-3 text-meta text-ink-3">
            {doing.key === "company" ? "Bishnoi One Platform is taking a while: it may be starting up." : "Taking longer than usual: the database may be waking up. This happens after a quiet spell, and takes a few seconds."}
          </p>
        )}
        {error && (
          <button
            type="button"
            onClick={() => onBack(error)}
            className="mt-8 flex h-12 w-full items-center justify-center rounded-lg bg-[#141414] text-sm font-medium text-white hover:bg-[#2b2b2b] focus-visible:ring-2 focus-visible:ring-[#a8d69b] focus-visible:ring-offset-2 focus-visible:outline-none"
            autoFocus
          >
            Back to sign in
          </button>
        )}
      </div>
    </div>
  );
}
