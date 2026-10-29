"use client";

import { Eraser } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/src/platform/ui/button";
import { cleanSignature, loadImage, type Cleaned } from "./clean";

// Signing, drawn or from a photo (decided 2026-10-22; shared since 2026-10-29, feature plan step 10):
// cleaned in the browser (paper made transparent, ink made black, trimmed); only the cleaned PNG is sent.
// Used for a person's own signature (their profile, Finance) and a customer signing for a delivery.

/** A light checkerboard, so a transparent signature reads as transparent. */
export const CHECKER = "bg-[length:16px_16px] bg-[linear-gradient(45deg,#f1f1f4_25%,transparent_25%),linear-gradient(-45deg,#f1f1f4_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f1f1f4_75%),linear-gradient(-45deg,transparent_75%,#f1f1f4_75%)] bg-white";

/** Sign with a mouse, finger or pen. Kept black; trimmed when saved. */
export function DrawPad({ onChange }: { onChange: (c: Cleaned | null) => void }) {
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
export function UploadPicker({ onChange }: { onChange: (c: Cleaned | null) => void }) {
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
