"use client";

import { Printer } from "lucide-react";
import { useState } from "react";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { preparePrintAttachments } from "./attachments";

/** Wait for logos and recorded signatures; never open a knowingly incomplete print. */
let activePrint: Promise<void> | undefined;
export function prepareFinancePrint(): Promise<void> {
  if (activePrint) return activePrint;
  activePrint = prepare().finally(() => { activePrint = undefined; });
  return activePrint;
}
async function prepare() {
  const root = document.querySelector<HTMLElement>(".finance-print-scope");
  if (root) await preparePrintAttachments(root);
  const images = Array.from(document.querySelectorAll<HTMLImageElement>(".finance-print-scope img"));
  await Promise.all(images.map((image) => new Promise<void>((resolve, reject) => {
    if (image.complete) {
      image.naturalWidth > 0 ? resolve() : reject(new Error("image"));
      return;
    }
    const finish = (ok: boolean) => {
      clearTimeout(timer);
      image.removeEventListener("load", loaded);
      image.removeEventListener("error", failed);
      ok ? resolve() : reject(new Error("image"));
    };
    const loaded = () => finish(true);
    const failed = () => finish(false);
    const timer = setTimeout(failed, 6000);
    image.addEventListener("load", loaded, { once: true });
    image.addEventListener("error", failed, { once: true });
  })));
  await document.fonts.ready;
  window.print();
}

export function FinancePrintButton({ label = "Print" }: { label?: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <span className="finance-print-action">
    <Button icon={<Printer className="size-4" aria-hidden />} loading={pending} onClick={async () => {
      if (pending) return;
      setPending(true);
      setError(null);
      try { await prepareFinancePrint(); }
      catch (error) { setError(error instanceof Error && error.message !== "image" ? error.message : "A logo, signature or attachment did not load. Refresh the document before printing."); }
      finally { setPending(false); }
    }}>{pending ? "Preparing print pages…" : label}</Button>
    {error && <span role="alert" className="block text-sm text-danger">{error}</span>}
  </span>;
}
