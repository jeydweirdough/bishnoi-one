"use client";

import { MessageSquare, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AssistantChat } from "./chat";

/** One instance in the signed-in layout keeps chat available across module navigation. */
export function FloatingAssistant({ companyId, companyName }: { companyId: string; companyName: string }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [started, setStarted] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const show = () => { setStarted(true); setOpen(true); };
  const minimize = () => { setOpen(false); trigger.current?.focus(); };

  // Preserve existing /assistant bookmarks, opening the same floating conversation.
  useEffect(() => {
    if (pathname === "/assistant") { setStarted(true); setOpen(true); }
  }, [pathname]);
  useEffect(() => {
    if (open) panel.current?.querySelector<HTMLTextAreaElement>("textarea")?.focus({ preventScroll: true });
  }, [open]);

  return <>
    {started && <section
      ref={panel}
      id="bishnoi-assistant-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="bishnoi-assistant-title"
      hidden={!open}
      onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); minimize(); } }}
      className={`fixed z-[60] flex-col overflow-hidden rounded-2xl border border-rule bg-sheet shadow-[0_16px_60px_rgba(20,20,20,0.22)] print:hidden ${open ? "flex" : "hidden"}`}
      style={{ bottom: "calc(5.5rem + env(safe-area-inset-bottom))", right: "max(1rem, env(safe-area-inset-right))", width: "min(27rem, calc(100vw - 2rem))", height: "min(40rem, calc(100dvh - 7rem - env(safe-area-inset-bottom)))" }}
    >
      <header className="flex shrink-0 items-center gap-3 border-b border-rule bg-ink px-4 py-3 text-white">
        <MessageSquare className="size-5 shrink-0 text-sage" aria-hidden />
        <div className="min-w-0 flex-1"><h2 id="bishnoi-assistant-title" className="text-sm font-semibold">Bishnoi assistant</h2><p className="truncate text-xs text-white/70">{companyName} / Read-only</p></div>
        <button type="button" aria-label="Minimize assistant" title="Minimize assistant" onClick={minimize} className="grid size-8 shrink-0 place-items-center rounded-lg hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"><X className="size-4" aria-hidden /></button>
      </header>
      <div className="min-h-0 flex-1"><AssistantChat companyId={companyId} companyName={companyName} embedded visible={open} /></div>
    </section>}
    <button
      ref={trigger}
      type="button"
      aria-label={open ? "Minimize company assistant" : "Open company assistant"}
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls={started ? "bishnoi-assistant-panel" : undefined}
      title={open ? "Minimize assistant" : "Ask Bishnoi assistant"}
      onClick={() => open ? minimize() : show()}
      className="fixed z-50 inline-flex h-14 items-center gap-2 rounded-full bg-ink px-4 text-white shadow-[0_6px_24px_rgba(20,20,20,0.22)] transition-colors hover:bg-ink/90 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink print:hidden"
      style={{ bottom: "max(1rem, env(safe-area-inset-bottom))", right: "max(1rem, env(safe-area-inset-right))" }}
    >
      {open ? <X className="size-5" aria-hidden /> : <MessageSquare className="size-5" aria-hidden />}
      <span className="text-sm font-semibold">{open ? "Minimize" : "Ask Bishnoi"}</span>
    </button>
  </>;
}
