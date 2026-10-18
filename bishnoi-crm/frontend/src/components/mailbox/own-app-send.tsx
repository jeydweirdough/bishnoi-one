"use client";

import { Check, Copy, ExternalLink, X } from "lucide-react";
import { FileDrop } from "@/src/platform/ui/file-drop";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, IconButton } from "@/src/platform/ui/button";
import { FormError } from "@/src/platform/ui/field";
import { logEmail, type EmailDraft } from "../../actions/mailbox";

type Ready = { to: string[]; subject: string; body: string };

/**
 * The email window's fallback, when the CRM can't send it itself (no mailbox
 * connected, or the provider refused): two steps.
 * 1. Copy it into your own email app: each part with Copy, and buttons that
 *    open Gmail, Zoho Mail or the computer's mail app with it filled in where they can.
 * 2. Sent? Attach a screenshot of it in your Sent folder (pick a file, or paste
 *    it with Ctrl+V), and it's logged on the customer with the screenshot as proof.
 */
export function OwnAppSend({ draft, ready, onLogged }: { draft: EmailDraft; ready: Ready; onLogged: () => void }) {
  const [copied, setCopied] = useState<string | null>(null);
  const [shot, setShot] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const to = ready.to.join(", ");

  useEffect(() => {
    if (!shot) return setPreview(null);
    const url = URL.createObjectURL(shot);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [shot]);

  // A screenshot pasted anywhere in the window (Ctrl+V) is taken as the proof.
  useEffect(() => {
    function paste(e: ClipboardEvent) {
      const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith("image/"));
      const file = item?.getAsFile();
      if (file) {
        setShot(new File([file], "screenshot.png", { type: file.type }));
        setError(null);
      }
    }
    window.addEventListener("paste", paste);
    return () => window.removeEventListener("paste", paste);
  }, []);

  async function copy(what: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
      setTimeout(() => setCopied((c) => (c === what ? null : c)), 1800);
    } catch {
      toast.error("Couldn't copy. Select the text and press Ctrl+C.");
    }
  }

  function pick(file: File | undefined) {
    if (!file) return;
    if (!file.type.startsWith("image/")) return setError("Attach a picture: a screenshot of the email in your Sent folder.");
    if (file.size > 4 * 1024 * 1024) return setError("The screenshot is over 4 MB. Take it again, or crop it to the email.");
    setShot(file);
    setError(null);
  }

  function log() {
    if (!shot) return setError("Attach a screenshot of the email in your Sent folder first.");
    start(async () => {
      const form = new FormData();
      form.set("proof", shot);
      const r = await logEmail(draft, form);
      if (!r.ok) return setError(r.fields ? Object.values(r.fields)[0] : r.error);
      toast.success("Email logged on the customer", { description: `${ready.subject}, with its screenshot` });
      onLogged();
    });
  }

  const gmail = `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(to)}&su=${encodeURIComponent(ready.subject)}&body=${encodeURIComponent(ready.body)}`;
  const mailto = `mailto:${ready.to.map(encodeURIComponent).join(",")}?subject=${encodeURIComponent(ready.subject)}&body=${encodeURIComponent(ready.body.slice(0, 1500))}`;

  const Part = ({ name, value, long = false }: { name: string; value: string; long?: boolean }) => (
    <div className="rounded-lg border border-rule bg-sheet px-3.5 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-meta font-medium text-ink-3">{name}</span>
        <button
          type="button"
          onClick={() => copy(name, value)}
          className="inline-flex items-center gap-1.5 rounded-md border border-rule-strong px-2.5 py-0.5 text-meta font-medium text-ink hover:border-ink hover:bg-mint"
        >
          {copied === name ? <Check className="size-3.5 text-sage-deep" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
          {copied === name ? "Copied" : "Copy"}
        </button>
      </div>
      <p className={`mt-1 text-sm text-ink ${long ? "max-h-40 overflow-y-auto whitespace-pre-line" : "truncate"}`}>{value}</p>
    </div>
  );

  return (
    <div className="space-y-5 pt-1">
      <section aria-labelledby="own-1">
        <h3 id="own-1" className="flex items-center gap-2 text-sm font-semibold text-ink">
          <span className="grid size-6 place-items-center rounded-full bg-ink text-[12px] text-white">1</span>
          Copy it into your own email
        </h3>
        <div className="mt-3 space-y-2">
          <Part name="To" value={to} />
          <Part name="Subject" value={ready.subject} />
          <Part name="Message" value={ready.body} long />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <a href="https://mail.zoho.com/zm/" target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ink bg-sheet px-3 text-sm font-medium text-ink hover:bg-mint">
            Open Zoho Mail <ExternalLink className="size-3.5" aria-hidden />
          </a>
          <a href={gmail} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ink bg-sheet px-3 text-sm font-medium text-ink hover:bg-mint">
            Open in Gmail <ExternalLink className="size-3.5" aria-hidden />
          </a>
          <a href={mailto} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-rule-strong bg-sheet px-3 text-sm text-ink-2 hover:border-ink hover:text-ink">
            My computer&apos;s mail app
          </a>
        </div>
        <p className="mt-2 text-meta text-ink-3">Gmail and your mail app open with it filled in; in Zoho Mail, start a new email and paste each part.</p>
      </section>

      <section aria-labelledby="own-2">
        <h3 id="own-2" className="flex items-center gap-2 text-sm font-semibold text-ink">
          <span className="grid size-6 place-items-center rounded-full bg-ink text-[12px] text-white">2</span>
          Sent? Attach a screenshot of it
        </h3>
        <p className="mt-1 text-meta text-ink-3">Open the email in your Sent folder and take a screenshot (Windows: Win+Shift+S), then paste it here with Ctrl+V or pick the file. It&apos;s kept on the customer as proof it went.</p>
        {preview ? (
          <div className="relative mt-3 overflow-hidden rounded-lg border border-rule">
            {/* eslint-disable-next-line @next/next/no-img-element -- a local preview of the picked file */}
            <img src={preview} alt="The screenshot to attach" className="max-h-56 w-full object-contain bg-bench" />
            <IconButton onClick={() => setShot(null)} label="Remove the screenshot" tone="solid" className="absolute top-2 right-2">
              <X className="size-4" aria-hidden />
            </IconButton>
          </div>
        ) : (
          <div className="mt-3">
            <FileDrop accept="image/png,image/jpeg,image/webp" note="Or paste it with Ctrl+V. PNG, JPG or WEBP" onFile={(f) => f && pick(f)} />
          </div>
        )}
      </section>

      <FormError message={error} />
      <div className="flex justify-end">
        <Button variant="primary" loading={pending} disabled={!shot} onClick={log}>
          Log it on the customer
        </Button>
      </div>
    </div>
  );
}
