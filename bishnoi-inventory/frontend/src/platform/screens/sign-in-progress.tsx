"use client";

import { Check, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { checkAccess } from "../actions/session";
import { thisAppLabel } from "../lib/apps";

// Signing in, shown as one calm "Please wait a moment" screen with a progress
// ring and the five steps. Each step is a real call, done when that call comes
// back, never on a timer; the ring only creeps forward within the step under
// way and stops short of its end, so it never reads 100% before the page is
// there. A step that fails says why and offers the form again.
//
// The same file is in every app's shared kit (src/platform/screens/sign-in-progress.tsx).

type State = "waiting" | "doing" | "done" | "failed";
type Key = "auth" | "profile" | "data" | "modules" | "open";
type Row = { key: Key; title: string; working: string; state: State };
// The share of the ring each step owns, and how quickly it creeps across it (seconds).
type Span = { from: number; to: number; pace: number; at: number };

const SLOW_AFTER = 8; // seconds: then it says why it may be slow
const LIMIT = 99; // the ring never shows 100%: this screen goes away when the page is ready

export function SignInProgress({ next, onBack }: { next: string; onBack: (error: string) => void }) {
  const router = useRouter();
  const app = thisAppLabel() ?? "Bishnoi One";
  const [rows, setRows] = useState<Row[]>([
    // Checked on the form already: this screen opens only for credentials that are right.
    { key: "auth", title: "Authenticating session", working: "Session authenticated", state: "done" },
    { key: "profile", title: "Loading user profile and permissions", working: "Reading your role and your apps…", state: "waiting" },
    { key: "data", title: "Fetching workspace data", working: "Fetching your first page…", state: "waiting" },
    { key: "modules", title: "Initializing application modules", working: "Loading fonts and pictures…", state: "waiting" },
    { key: "open", title: "Opening your workspace", working: "Opening your workspace…", state: "waiting" },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [percent, setPercent] = useState(30);
  const span = useRef<Span>({ from: 30, to: 48, pace: 1.5, at: Date.now() });
  const startedAt = useRef<number>(Date.now());
  const ran = useRef(false);

  const set = (key: Key, change: Partial<Row>) => setRows((all) => all.map((r) => (r.key === key ? { ...r, ...change } : r)));
  // The ring moves on to a step's share of it (never backwards: see the tick).
  const spanTo = (from: number, to: number, pace: number) => {
    span.current = { from, to, pace, at: Date.now() };
    setPercent((p) => Math.max(p, from));
  };

  // A tick, so the ring creeps (easing towards the end of the step's share, never
  // reaching it) and the step under way can say how long it has taken. It stops on a failure.
  useEffect(() => {
    if (error) return;
    const t = setInterval(() => {
      const at = Date.now();
      const { from, to, pace } = span.current;
      const creep = 1 - Math.exp(-Math.max(0, at - span.current.at) / 1000 / pace);
      setNow(at);
      setPercent((p) => Math.min(LIMIT, Math.max(p, Math.floor(from + (to - from) * creep))));
    }, 250);
    return () => clearInterval(t);
  }, [error]);

  useEffect(() => {
    if (ran.current) return; // once, even when React runs effects twice in development
    ran.current = true;
    const unanswered = "Bishnoi One didn't answer. Check your connection, and try again.";
    const fail = (key: Key, why: string) => {
      set(key, { state: "failed" });
      setError(why);
    };
    // Done: { data }. Failed: undefined (the screen already says why).
    async function step<T>(key: Key, run: () => Promise<{ ok: true; data: T } | { ok: false; error: string }>): Promise<{ data: T } | undefined> {
      const r = await run().catch(() => ({ ok: false as const, error: unanswered }));
      if (!r.ok) return void fail(key, r.error);
      return { data: r.data };
    }
    const begin = (key: Key, from: number, to: number, pace: number) => {
      startedAt.current = Date.now();
      set(key, { state: "doing" });
      spanTo(from, to, pace);
    };

    (async () => {
      // 1. Authenticating: done on the sign-in form before this screen opens.
      // 2. Their role, and which app is theirs.
      begin("profile", 30, 48, 1.5);
      const access = await step("profile", () => checkAccess(next));
      if (!access) return;
      const where = access.data;
      set("profile", { state: "done" });

      // 3. The first page, asked for once with the new session: it warms the page
      // up, and shows the session took. Another app's page is opened as it is.
      begin("data", 48, 74, 3);
      if (!where.elsewhere && !(await step("data", () => warm(where.go)))) return;
      set("data", { state: "done" });

      // 4. Real waits: the fonts in use, and the logo, loaded in this browser.
      begin("modules", 74, 86, 1);
      await Promise.all([document.fonts.ready, logoLoaded()]);
      set("modules", { state: "done" });

      // 5. Done when the page appears: this screen goes away with it.
      begin("open", 86, LIMIT, 3);
      if (where.elsewhere) window.location.assign(where.go);
      else {
        router.replace(where.go);
        router.refresh();
      }
    })().catch(() => {
      setRows((all) => all.map((r) => (r.state === "doing" ? { ...r, state: "failed" } : r)));
      setError(unanswered);
    });
  }, [app, next, router]);

  const doing = rows.find((r) => r.state === "doing");
  const elapsed = doing ? Math.max(0, Math.floor((now - startedAt.current) / 1000)) : 0;
  const index = rows.findIndex((r) => r.state === "doing" || r.state === "failed");
  const step = index >= 0 ? index + 1 : Math.max(1, rows.filter((r) => r.state === "done").length);
  const R = 46;
  const C = 2 * Math.PI * R;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="signing-in"
      className="fixed inset-0 z-50 overflow-y-auto bg-gradient-to-b from-sheet via-sheet to-hema-tint px-4"
    >
      <div className="mx-auto flex min-h-full w-full max-w-sm flex-col items-center justify-center py-10 text-center">
        {/* A soft halo, the progress ring, and the mark in the middle. */}
        <div
          role="progressbar"
          aria-label="Signing in"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className="relative grid size-32 place-items-center rounded-full bg-hema-tint/60 ring-1 ring-sage/30 sm:size-40"
        >
          <div className="absolute inset-3 rounded-full bg-sheet/70 ring-1 ring-sage/25" />
          <svg viewBox="0 0 100 100" className="absolute inset-0 size-full -rotate-90" aria-hidden>
            <circle cx="50" cy="50" r={R} fill="none" stroke="var(--color-sage)" strokeOpacity="0.25" strokeWidth="2.5" />
            <circle
              cx="50"
              cy="50"
              r={R}
              fill="none"
              stroke={error ? "var(--color-danger)" : "var(--color-sage-deep)"}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeDasharray={C}
              strokeDashoffset={C * (1 - percent / 100)}
              className="transition-[stroke-dashoffset,stroke] duration-300 ease-out motion-reduce:transition-none"
            />
          </svg>
          <span className={`relative grid size-16 place-items-center rounded-full shadow-sheet transition-colors duration-300 sm:size-20 ${error ? "bg-danger" : "bg-sage-deep"}`}>
            {error ? (
              <X className="size-7 text-white sm:size-8" strokeWidth={2.5} />
            ) : (
              <img src="/brand/bishnoi-one-mark.png" alt="" width={40} height={40} className="size-8 brightness-0 invert sm:size-10" />
            )}
          </span>
        </div>

        <p className={`mt-5 text-2xl font-semibold tabular-nums ${error ? "text-danger" : "text-sage-deep"}`} aria-hidden>
          {percent}%
        </p>
        <h1 id="signing-in" className="mt-3 text-xl font-semibold text-ink sm:text-2xl">
          {error ? "Sign-in failed" : "Please wait a moment"}
        </h1>
        <p className="mt-2 min-h-5 text-sm text-ink-2" aria-live="polite">
          {error ?? doing?.working ?? `Signing you in to Bishnoi One ${app}…`}
        </p>
        <p className="mt-2 text-meta text-ink-3 tabular-nums">
          Step {step} of {rows.length}
          {!error && elapsed > 0 && ` · ${elapsed}s`}
        </p>
        {doing && elapsed >= SLOW_AFTER && <p className="mt-2 text-meta text-ink-3">{slowNote(doing.key)}</p>}

        <ol className="mt-7 w-full space-y-1 text-left">
          {rows.map((r) => (
            <li
              key={r.key}
              aria-current={r.state === "doing" ? "step" : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-300 ${
                r.state === "doing" ? "bg-hema-tint/70 font-medium text-ink ring-1 ring-sage/30" : r.state === "failed" ? "bg-danger/5 font-medium text-danger" : r.state === "done" ? "text-ink-2" : "text-ink-3"
              }`}
            >
              <span
                className={`grid size-5 shrink-0 place-items-center rounded-full transition-colors duration-300 ${
                  r.state === "done" ? "bg-sage-deep text-white" : r.state === "failed" ? "bg-danger text-white" : r.state === "doing" ? "ring-2 ring-sage-deep" : "ring-1 ring-ink-3/40"
                }`}
                aria-hidden
              >
                {r.state === "done" && <Check className="size-3" strokeWidth={3} />}
                {r.state === "failed" && <X className="size-3" strokeWidth={3} />}
                {r.state === "doing" && <span className="size-2 animate-pulse rounded-full bg-sage-deep motion-reduce:animate-none" />}
              </span>
              <span className="min-w-0 flex-1">{r.title}</span>
              <span className="sr-only">{r.state === "done" ? "(done)" : r.state === "doing" ? "(under way)" : r.state === "failed" ? "(failed)" : "(to come)"}</span>
            </li>
          ))}
        </ol>

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

function slowNote(key: Key) {
  if (key === "data" || key === "open") return "Your first page is taking a while: it may be getting ready for the first time today.";
  return "Taking longer than usual: the database may be waking up. This happens after a quiet spell, and takes a few seconds.";
}

/** The first page, asked for with the new session. Sent back to sign-in means the session didn't take. */
async function warm(go: string): Promise<{ ok: true; data: null } | { ok: false; error: string }> {
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), 20_000);
  try {
    const res = await fetch(go, { credentials: "same-origin", signal: stop.signal, headers: { accept: "text/html" } });
    res.body?.cancel().catch(() => undefined); // the answer is enough; the page itself comes with the navigation
    if (new URL(res.url).pathname.endsWith("/login")) {
      return { ok: false, error: "Your session didn't open. Sign in again, and if it keeps happening, check that this browser allows cookies for this site." };
    }
  } catch {
    // Slow or unanswered: opening the page says so, so go on.
  } finally {
    clearTimeout(timer);
  }
  return { ok: true, data: null };
}

function logoLoaded() {
  const logo = new Image();
  logo.src = "/brand/bishnoi-one-mark.png";
  return logo.decode().catch(() => undefined);
}
