"use client";

import { Eraser, PenLine, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Field, FormError, Input } from "@/src/modules/finance/platform/ui/field";
import { Modal } from "@/src/modules/finance/platform/ui/modal";
import { SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { removeSignature, setSignature } from "@/src/modules/finance/signature/actions";
import { cleanSignature, loadImage, type Cleaned } from "@/src/modules/finance/signature/clean";
import type { MySignature } from "@/src/modules/finance/signature/types";

// Your e-signature, on your account page (decided 2026-10-22: Plans/Plan - E-signatures).
// Drawn or uploaded; cleaned here, in your browser; black ink. Finance places it on the
// documents you prepare, approve, review or settle, and nowhere else.

/** A light checkerboard, so a transparent signature reads as transparent. */
const CHECKER = "bg-[length:16px_16px] bg-[linear-gradient(45deg,#f1f1f4_25%,transparent_25%),linear-gradient(-45deg,#f1f1f4_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f1f1f4_75%),linear-gradient(-45deg,transparent_75%,#f1f1f4_75%)] bg-white";

export function SignatureCard({ data }: { data: MySignature }) {
  const [mode, setMode] = useState<"draw" | "upload" | "remove" | null>(null);
  const c = data.current;
  return (
    <Sheet className="mt-5 px-5 py-4">
      <SectionTitle icon="particulars">Your e-signature</SectionTitle>
      <p className="mb-3 max-w-2xl text-sm text-ink-2">
        Finance places it on the documents you prepare, approve, review or settle (journal vouchers, liquidation reports), with your name, the date and a reference. Only you
        can set it.
      </p>
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
      {mode && <SignatureDialog mode={mode} data={data} onClose={() => setMode(null)} />}
    </Sheet>
  );
}

function SignatureDialog({ mode, data, onClose }: { mode: "draw" | "upload" | "remove"; data: MySignature; onClose: () => void }) {
  const [cleaned, setCleaned] = useState<Cleaned | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const byPassword = data.confirmBy === "password";
  const blocked = !byPassword && !data.recentSignIn;

  function save() {
    start(async () => {
      const r = mode === "remove" ? await removeSignature(password) : cleaned ? await setSignature(cleaned.dataUrl, mode === "draw" ? "drawn" : "uploaded", password) : null;
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
    <Modal open title={title} onCancel={onClose} footer={null} width={640}>
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
          <Button variant={mode === "remove" ? "danger" : "primary"} loading={pending} disabled={blocked} onClick={save}>
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

/** Sign with a mouse, finger or pen. Kept black; trimmed when saved. */
function DrawPad({ onChange }: { onChange: (c: Cleaned | null) => void }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const drawing = useRef<{ x: number; y: number } | null>(null);
  const [inked, setInked] = useState(false);

  useEffect(() => {
    const ctx = ref.current?.getContext("2d");
    if (!ctx) return;
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#000";
  }, []);

  function at(e: React.PointerEvent<HTMLCanvasElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    return { x: ((e.clientX - r.left) / r.width) * e.currentTarget.width, y: ((e.clientY - r.top) / r.height) * e.currentTarget.height };
  }

  function finish() {
    drawing.current = null;
    if (ref.current && inked) onChange(cleanSignature(ref.current));
  }

  function clear() {
    const c = ref.current!;
    c.getContext("2d")!.clearRect(0, 0, c.width, c.height);
    setInked(false);
    onChange(null);
  }

  return (
    <div>
      <canvas
        ref={ref}
        width={900}
        height={300}
        aria-label="Signing pad: sign here"
        className="h-48 w-full touch-none rounded-[3px] border border-rule-strong bg-white"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          drawing.current = at(e);
        }}
        onPointerMove={(e) => {
          if (!drawing.current) return;
          const ctx = e.currentTarget.getContext("2d")!;
          const p = at(e);
          ctx.beginPath();
          ctx.moveTo(drawing.current.x, drawing.current.y);
          ctx.lineTo(p.x, p.y);
          ctx.stroke();
          drawing.current = p;
          if (!inked) setInked(true);
        }}
        onPointerUp={finish}
        onPointerLeave={() => drawing.current && finish()}
      />
      <div className="mt-1 flex items-center justify-between">
        <p className="text-meta text-ink-3">Sign inside the box.</p>
        <Button size="sm" variant="quiet" icon={<Eraser className="size-4" aria-hidden />} onClick={clear}>
          Clear
        </Button>
      </div>
    </div>
  );
}

/** A photo or scan: cleaned here (paper made transparent, ink made black), with a slider to adjust. */
function UploadPicker({ onChange }: { onChange: (c: Cleaned | null) => void }) {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [strength, setStrength] = useState(0.5);
  const [result, setResult] = useState<Cleaned | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (!img) return;
    const c = cleanSignature(img, strength);
    setResult(c);
    onChange(c.empty ? null : c);
  }, [img, strength, onChange]);

  return (
    <div className="space-y-3">
      <input suppressHydrationWarning
        type="file"
        accept="image/png,image/jpeg"
        aria-label="Choose a photo or scan of your signature"
        className="block text-sm"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          setProblem(null);
          if (!file) return;
          if (file.size > 15_000_000) return setProblem("That picture is too large. Use one under 15 MB.");
          try {
            setImg(await loadImage(file));
          } catch (err) {
            setProblem((err as Error).message);
          }
        }}
      />
      <p className="text-meta text-ink-3">Tip: sign on plain white paper, take the photo in good light, from straight above. It's cleaned here, on your computer; the photo itself isn't sent.</p>
      {problem && <p className="text-meta text-danger">{problem}</p>}
      {result && (
        <>
          <div className={`flex min-h-28 items-center justify-center rounded-[3px] border border-rule p-3 ${CHECKER}`}>
            {result.empty ? (
              <p className="text-meta text-danger">No signature found. Try &quot;Keep more&quot;, or a clearer photo.</p>
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={result.dataUrl} alt="Your signature, cleaned" className="max-h-32 max-w-full object-contain" />
            )}
          </div>
          {result.wasTransparent ? (
            <p className="text-meta text-ink-3">This picture is already transparent: it's only trimmed, resized and made black.</p>
          ) : (
            <label className="flex items-center gap-3 text-meta text-ink-2">
              Keep more
              <input suppressHydrationWarning type="range" min={0} max={1} step={0.05} value={strength} onChange={(e) => setStrength(Number(e.target.value))} className="flex-1 accent-[var(--color-hema)]" aria-label="How much of the picture counts as paper" />
              Cleaner
            </label>
          )}
        </>
      )}
    </div>
  );
}
