"use client";

import { Eraser, ImagePlus, PenLine, Trash2, Upload } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { removeTemplateImage, uploadTemplateFile } from "@/src/actions/quote-templates";
import { Button } from "@/src/platform/ui/button";
import type { QuoteTemplate } from "./types";

/** The template's logo or e-signature as it is now, with the ways to change it. */
export function TemplateImage({
  template,
  which,
  onSaved,
}: {
  template: QuoteTemplate;
  which: "logo" | "signature";
  onSaved: (t: QuoteTemplate) => void;
}) {
  const has = which === "logo" ? template.hasLogo : template.hasSignature;
  const [drawing, setDrawing] = useState(false);
  const [pending, start] = useTransition();
  const [version, setVersion] = useState(0); // bumped after a change, so the new image is fetched
  const file = useRef<HTMLInputElement>(null);
  const noun = which === "logo" ? "logo" : "e-signature";

  function send(blob: Blob, name: string) {
    const form = new FormData();
    form.set("file", new File([blob], name, { type: blob.type || "image/png" }));
    start(async () => {
      const r = await uploadTemplateFile(template.id, which, form);
      if (!r.ok) return void toast.error(`The ${noun} wasn't saved`, { description: r.error });
      setVersion(Date.now());
      setDrawing(false);
      onSaved(r.data);
      toast.success(`${which === "logo" ? "Logo" : "E-signature"} saved`);
    });
  }

  function remove() {
    start(async () => {
      const r = await removeTemplateImage(template.id, which);
      if (!r.ok) return void toast.error(`The ${noun} wasn't removed`, { description: r.error });
      onSaved(r.data);
    });
  }

  return (
    <div className="space-y-3">
      <div className={`flex items-center justify-center rounded-[6px] border border-dashed border-rule-strong bg-white ${which === "logo" ? "h-28" : "h-24"}`}>
        {has ? (
          // eslint-disable-next-line @next/next/no-img-element -- a stored file, sized by its own proportions
          <img src={`/quote-templates/${template.id}/images/${which}?v=${version}`} alt={`The ${noun}`} className="max-h-full max-w-full object-contain p-2" />
        ) : (
          <span className="text-meta text-ink-3">No {noun} yet</span>
        )}
      </div>
      {drawing && which === "signature" ? (
        <SignaturePad busy={pending} onDone={(blob) => send(blob, "signature.png")} onCancel={() => setDrawing(false)} />
      ) : (
        <div className="flex flex-wrap gap-2">
          <input
            ref={file}
            type="file"
            accept="image/png,image/jpeg"
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) send(f, f.name);
              e.target.value = "";
            }}
          />
          <Button size="sm" loading={pending} icon={which === "logo" ? <ImagePlus className="size-4" aria-hidden /> : <Upload className="size-4" aria-hidden />} onClick={() => file.current?.click()}>
            {has ? "Replace" : "Upload"} {which === "logo" ? "logo" : "image"}
          </Button>
          {which === "signature" && (
            <Button size="sm" icon={<PenLine className="size-4" aria-hidden />} onClick={() => setDrawing(true)}>
              Draw signature
            </Button>
          )}
          {has && (
            <Button size="sm" variant="quiet" icon={<Trash2 className="size-4" aria-hidden />} onClick={remove} disabled={pending}>
              Remove
            </Button>
          )}
        </div>
      )}
      <p className="text-meta text-ink-3">
        {which === "logo"
          ? "PNG or JPG, up to 2 MB. It goes on the top left of the quotation."
          : "PNG or JPG with a white or clear background, or draw it here. It goes above the authorized representative's name."}
      </p>
    </div>
  );
}

/** Draw a signature with a mouse, a finger or a pen. Saved as a PNG with a clear background. */
function SignaturePad({ busy, onDone, onCancel }: { busy: boolean; onDone: (blob: Blob) => void; onCancel: () => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const last = useRef<{ x: number; y: number } | null>(null);
  const [empty, setEmpty] = useState(true);

  const point = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const scale = e.currentTarget.width / box.width;
    return { x: (e.clientX - box.left) * scale, y: (e.clientY - box.top) * scale };
  };

  function stroke(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!last.current) return;
    const ctx = e.currentTarget.getContext("2d");
    if (!ctx) return;
    const p = point(e);
    ctx.strokeStyle = "#0b1f4d";
    ctx.lineWidth = 3.2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(last.current.x, last.current.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last.current = p;
    setEmpty(false);
  }

  function clear() {
    const c = canvas.current;
    c?.getContext("2d")?.clearRect(0, 0, c.width, c.height);
    setEmpty(true);
  }

  return (
    <div className="space-y-2">
      <canvas
        ref={canvas}
        width={900}
        height={260}
        aria-label="Signature pad: draw your signature"
        className="h-32 w-full touch-none rounded-[6px] border border-control bg-white"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          last.current = point(e);
        }}
        onPointerMove={stroke}
        onPointerUp={() => (last.current = null)}
        onPointerLeave={() => (last.current = null)}
      />
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="primary"
          loading={busy}
          disabled={empty}
          onClick={() => canvas.current?.toBlob((blob) => blob && onDone(blob), "image/png")}
        >
          Save signature
        </Button>
        <Button size="sm" icon={<Eraser className="size-4" aria-hidden />} onClick={clear} disabled={empty}>
          Clear
        </Button>
        <Button size="sm" variant="quiet" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
