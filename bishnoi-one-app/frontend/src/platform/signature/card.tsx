"use client";

import { Modal } from "antd";
import { PenLine, Trash2, Upload } from "lucide-react";
import { useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import type { Cleaned } from "./clean";
import { CHECKER, DrawPad, UploadPicker } from "./pads";

// A person's own e-signature (decided 2026-10-22; shared since 2026-10-29, feature plan step 10): drawn or
// uploaded, cleaned in the browser, black ink. Where it's kept (their Bishnoi One profile, or Finance) gives
// the save and remove; only they can set it.

export type MySignature = {
  current: { method: "drawn" | "uploaded" | string; setAt: string; image: string } | null;
  /** How a change is confirmed: their password, or (signed in with Bishnoi One) a recent sign-in. */
  confirmBy: "password" | "recent_sign_in";
  recentSignIn: boolean;
};

type Result = { ok: true } | { ok: false; error: string; fields?: Record<string, string> };

export function SignatureCard({ data, intro, save, remove }: {
  data: MySignature;
  intro: ReactNode;
  save: (image: string, method: "drawn" | "uploaded", password: string | null) => Promise<Result>;
  remove: (password: string | null) => Promise<Result>;
}) {
  const [mode, setMode] = useState<"draw" | "upload" | "remove" | null>(null);
  const c = data.current;
  return (
    <Sheet className="mt-5 px-5 py-4">
      <SectionTitle icon="particulars">Your e-signature</SectionTitle>
      <p className="mb-3 max-w-2xl text-sm text-ink-2">{intro}</p>
      {c ? (
        <div className="flex flex-wrap items-end gap-4">
          <div className={`rounded-[3px] border border-rule px-4 py-3 ${CHECKER}`}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={c.image} alt="Your signature" className="h-16 max-w-72 object-contain" />
          </div>
          <p className="text-meta text-ink-3">
            {c.method === "drawn" ? "Drawn" : "Uploaded"} on {new Date(c.setAt).toLocaleDateString("en-PH", { day: "numeric", month: "short", year: "numeric" })}
          </p>
        </div>
      ) : (
        <p className="text-sm text-ink-3">No signature yet. Documents you sign will show your name only.</p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant={c ? "default" : "primary"} icon={<PenLine className="size-4" aria-hidden />} onClick={() => setMode("draw")}>
          {c ? "Draw a new one" : "Draw it"}
        </Button>
        <Button size="sm" icon={<Upload className="size-4" aria-hidden />} onClick={() => setMode("upload")}>
          Upload a photo or scan
        </Button>
        {c && (
          <Button size="sm" variant="quiet" icon={<Trash2 className="size-4" aria-hidden />} onClick={() => setMode("remove")}>
            Remove
          </Button>
        )}
      </div>
      {mode && <SignatureDialog mode={mode} data={data} save={save} remove={remove} onClose={() => setMode(null)} />}
    </Sheet>
  );
}

function SignatureDialog({ mode, data, save, remove, onClose }: {
  mode: "draw" | "upload" | "remove";
  data: MySignature;
  save: (image: string, method: "drawn" | "uploaded", password: string | null) => Promise<Result>;
  remove: (password: string | null) => Promise<Result>;
  onClose: () => void;
}) {
  const [cleaned, setCleaned] = useState<Cleaned | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const byPassword = data.confirmBy === "password";
  const blocked = !byPassword && !data.recentSignIn;

  function go() {
    start(async () => {
      const r = mode === "remove" ? await remove(password) : cleaned ? await save(cleaned.dataUrl, mode === "draw" ? "drawn" : "uploaded", password) : null;
      if (!r) return setError(mode === "draw" ? "Sign in the box first." : "Choose a picture first.");
      if (!r.ok) return setError(r.fields?.password ?? r.fields?.image ?? r.error);
      toast.success(mode === "remove" ? "Signature removed" : "Signature saved", {
        description: mode === "remove" ? "Documents you already signed keep it." : "It will appear on the documents you sign from now on.",
      });
      onClose();
    });
  }

  const title = mode === "draw" ? "Draw your signature" : mode === "upload" ? "Upload your signature" : "Remove your signature?";
  return (
    <Modal open title={title} onCancel={onClose} footer={null} width={640} destroyOnHidden>
      <div className="mt-3 space-y-4">
        {mode === "draw" && <DrawPad onChange={setCleaned} />}
        {mode === "upload" && <UploadPicker onChange={setCleaned} />}
        {mode === "remove" && <p className="text-sm text-ink-2">From now on, documents you sign show your name only. Documents you already signed keep this signature.</p>}
        {byPassword ? (
          <Field label="Your password" hint="To confirm it's you.">
            {(p) => <Input {...p} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
          </Field>
        ) : (
          <p className={`text-meta ${blocked ? "text-danger" : "text-ink-3"}`}>
            {blocked
              ? "You sign in with your Bishnoi One account. For your safety, sign out and sign in again, then do this within 15 minutes."
              : "You signed in recently with your Bishnoi One account, which confirms it's you."}
          </p>
        )}
        <FormError message={error} />
        <div className="flex gap-2">
          <Button variant={mode === "remove" ? "danger" : "primary"} loading={pending} disabled={blocked} onClick={go}>
            {mode === "remove" ? "Remove" : "Save signature"}
          </Button>
          <Button variant="quiet" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  );
}
