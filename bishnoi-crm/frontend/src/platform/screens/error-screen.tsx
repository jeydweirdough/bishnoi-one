import type { ReactNode } from "react";
import { ErrorArt, type ErrorArtKind } from "./error-art";

// Every error page in Bishnoi One, one way: what happened, in plain words, and
// what to do next. Never the error itself: its text can name a table, a file
// or a setting, which helps nobody but someone looking for a way in. What
// helps support is the reference, which finds the full error in the log.
// Laid out as the UI kit's error pages (decided 2026-10-22): its drawing, the
// code in small capitals, a large title, a line or two, the next steps.
//
// The same file is in every app's shared kit (src/platform/screens/error-screen.tsx).

export type ErrorKind = "notFound" | "forbidden" | "busy" | "unavailable" | "failed" | "crashed";

const SAY: Record<ErrorKind, { code: string; title: string; body: string; art: ErrorArtKind }> = {
  notFound: {
    code: "Error 404",
    title: "We can't find that page",
    body: "That page doesn't exist, or it belongs to a team you can't see. Check the address, or start again from home.",
    art: "notFound",
  },
  forbidden: {
    code: "403 · Access denied",
    title: "You don't have access to this page",
    body: "Your role, or your company's Bishnoi One plan, doesn't include it. If you need it for your work, ask your administrator.",
    art: "forbidden",
  },
  busy: {
    code: "429 · Too many requests",
    title: "Give it a few seconds",
    body: "Too many requests came in a short time, so we paused them to keep things running for everyone. Wait a few seconds, then try again.",
    art: "maintenance",
  },
  unavailable: {
    code: "503 · Being updated",
    title: "We'll be right back",
    body: "The system isn't answering just now: it may be starting up or being updated. Nothing you did caused this. Try again in a minute.",
    art: "maintenance",
  },
  failed: {
    code: "Error 500",
    title: "Something went wrong on our side",
    body: "This page couldn't load. Your work is saved. Try again; if it keeps happening, tell your administrator, with the reference below.",
    art: "failed",
  },
  crashed: {
    code: "Error 500",
    title: "Something went wrong",
    body: "The app ran into a problem it couldn't recover from. Reload the page; if it keeps happening, tell your administrator, with the reference below.",
    art: "failed",
  },
};

/** An error page: its drawing, what happened, what to do, and the reference for support. `actions` are its buttons. */
export function ErrorScreen({ kind, reference, actions, standalone = false }: { kind: ErrorKind; reference?: string; actions?: ReactNode; standalone?: boolean }) {
  const say = SAY[kind];
  return (
    <main className={`flex items-center justify-center px-4 ${standalone ? "min-h-dvh" : "min-h-[60dvh]"}`}>
      <div className="w-full max-w-lg rounded-xl border border-rule bg-sheet px-6 pt-8 pb-9 text-center shadow-sheet sm:px-10">
        <ErrorArt kind={say.art} className="mx-auto h-[150px] w-[212px]" />
        <p className="mt-4 text-[0.8125rem] leading-none font-semibold tracking-[0.12em] text-ink-3 uppercase">{say.code}</p>
        <h1 className="mt-3 text-[1.5rem] leading-[1.25] font-semibold tracking-[-0.02em] text-balance text-ink">{say.title}</h1>
        <p className="mx-auto mt-2 max-w-[24rem] text-sm leading-[1.5] text-ink-2">{say.body}</p>
        {actions && <div className="mt-6 flex flex-wrap items-center justify-center gap-2">{actions}</div>}
        {reference && (
          <p className="mt-6 text-meta text-ink-3">
            Reference: <span className="font-mono text-ink-2 select-all">{reference}</span>
          </p>
        )}
      </div>
    </main>
  );
}

/** A button-shaped link that needs no app frame around it (the crash page has none), in the kit's shape. */
export const plainButton = (primary = false) =>
  `inline-flex h-10 items-center justify-center rounded-[9px] px-[18px] text-sm font-medium transition-colors ${primary ? "bg-ink text-white hover:bg-[#2b2b2b]" : "border border-[#dededa] bg-sheet text-ink shadow-[0_1px_2px_rgba(20,20,20,0.05)] hover:border-[#c9c9c5] hover:bg-[#f4f4f2]"}`;
