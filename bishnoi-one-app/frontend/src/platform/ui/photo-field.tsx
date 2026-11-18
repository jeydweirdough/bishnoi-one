"use client";

import { Camera, ImagePlus, Trash2 } from "lucide-react";
import { useId, useRef, useState } from "react";
import { Button, Spinner } from "./button";

// One way to add photos to a record (Step 4B, 2026-11-18): deliveries, proof of delivery, packages, field visits.
// Take one with the camera, upload, or drop them on it; never required. Large pictures are shrunk here to about
// 1600 px (JPEG) before they're sent, so uploads stay small on a phone's data. Kept photos show as thumbnails that
// open full size.
//
// Two ways to use it:
// - `upload` (a record that exists): each photo is sent as soon as it's picked; `remove` takes one off.
// - `onChange` (a form whose record isn't made yet): the photos are held here, then sent with `sendPhotos`
//   once the record is saved.

export type PhotoItem = { id: string; href: string; takenBy?: { name: string } | null; createdAt?: string; canRemove?: boolean };
type Outcome<T = unknown> = { ok: true; data: T } | { ok: false; error: string };

const KINDS = ["image/jpeg", "image/png", "image/webp"];
const SIDE = 1600;
const MAX_BYTES = 3_000_000;

/** A picture made smaller for sending: its longest side at most 1600 px, as a JPEG. Small JPEG/PNG/WebP files go as they are. */
export async function shrinkPhoto(file: File, side = SIDE, quality = 0.85): Promise<File> {
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) return file;
  const scale = Math.min(1, side / Math.max(bitmap.width, bitmap.height));
  if (scale === 1 && file.size <= 1_500_000 && KINDS.includes(file.type)) {
    bitmap.close();
    return file;
  }
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const blob = await new Promise<Blob | null>((done) => canvas.toBlob(done, "image/jpeg", quality));
  if (!blob) return file;
  return new File([blob], `${file.name.replace(/\.[^.]+$/, "") || "photo"}.jpg`, { type: "image/jpeg" });
}

/** Photos held by a form, sent once its record is saved. Says how many couldn't be sent (the record is kept either way). */
export async function sendPhotos(files: File[], upload: (form: FormData) => Promise<Outcome>): Promise<number> {
  let failed = 0;
  for (const file of files) {
    const form = new FormData();
    form.append("file", file);
    const r = await upload(form).catch(() => ({ ok: false as const, error: "" }));
    if (!r.ok) failed += 1;
  }
  return failed;
}

type Props = {
  /** Photos already kept with the record. */
  photos?: PhotoItem[];
  /** At most this many, kept and new together. */
  max?: number;
  label?: string;
  /** Sends one photo (FormData with "file") for a record that exists. */
  upload?: (form: FormData) => Promise<Outcome<PhotoItem>>;
  /** Takes a kept photo off. */
  remove?: (id: string) => Promise<Outcome>;
  /** A form's record isn't made yet: the photos picked, shrunk, to send after saving. */
  onChange?: (files: File[]) => void;
  disabled?: boolean;
  /** Only shows the kept photos (someone who may not add any); nothing when there are none. */
  readOnly?: boolean;
};

export function AddPhoto({ photos = [], max = 5, label = "Photo (optional)", upload, remove, onChange, disabled = false, readOnly = false }: Props) {
  const id = useId();
  const camera = useRef<HTMLInputElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const [added, setAdded] = useState<PhotoItem[]>([]);
  const [removed, setRemoved] = useState<string[]>([]);
  const [held, setHeld] = useState<{ file: File; url: string }[]>([]);
  const [sending, setSending] = useState(0);
  const [over, setOver] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const kept = [...photos, ...added.filter((a) => !photos.some((p) => p.id === a.id))].filter((p) => !removed.includes(p.id));
  const count = kept.length + held.length + sending;
  const room = Math.max(0, max - count);
  const locked = disabled || room === 0;

  async function take(list: File[]) {
    setProblem(null);
    const images = list.filter((f) => f.type.startsWith("image/"));
    if (images.length < list.length) setProblem("Only pictures can be added here.");
    if (images.length > room) setProblem(`${max} photos at most here.`);
    const chosen = images.slice(0, room);
    if (!chosen.length) return;
    const ready: File[] = [];
    for (const f of chosen) {
      const small = await shrinkPhoto(f);
      if (!KINDS.includes(small.type)) setProblem(`${f.name} couldn't be read as a picture. Use a JPEG, PNG or WebP.`);
      else if (small.size > MAX_BYTES) setProblem(`${f.name} is too large even made smaller.`);
      else ready.push(small);
    }
    if (!ready.length) return;
    if (!upload) {
      const next = [...held, ...ready.map((file) => ({ file, url: URL.createObjectURL(file) }))];
      setHeld(next);
      onChange?.(next.map((h) => h.file));
      return;
    }
    setSending((n) => n + ready.length);
    for (const file of ready) {
      const form = new FormData();
      form.append("file", file);
      const r = await upload(form).catch(() => ({ ok: false as const, error: "The photo couldn't be sent. Try again." }));
      setSending((n) => n - 1);
      if (r.ok) setAdded((a) => [...a, r.data]);
      else setProblem(r.error);
    }
  }

  async function drop(p: PhotoItem) {
    if (!remove) return;
    setProblem(null);
    setRemoved((r) => [...r, p.id]);
    const r = await remove(p.id);
    if (!r.ok) {
      setRemoved((x) => x.filter((i) => i !== p.id));
      setProblem(r.error);
    }
  }

  function unhold(i: number) {
    URL.revokeObjectURL(held[i].url);
    const next = held.filter((_, j) => j !== i);
    setHeld(next);
    onChange?.(next.map((h) => h.file));
  }

  if (readOnly) {
    if (!photos.length) return null;
    return (
      <ul className="flex flex-wrap gap-2" aria-label="Photos">
        {photos.map((p, i) => (
          <li key={p.id} className="size-16 shrink-0 overflow-hidden rounded-lg border border-rule bg-bench">
            <a href={p.href} target="_blank" rel="noreferrer" className="block size-full" title="Open full size">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={p.href} alt={`Photo ${i + 1}${p.takenBy ? `, by ${p.takenBy.name}` : ""}`} className="size-full object-cover" loading="lazy" />
            </a>
          </li>
        ))}
      </ul>
    );
  }

  const tile = "relative size-24 shrink-0 overflow-hidden rounded-lg border border-rule bg-bench";
  const removeButton = "absolute top-0 right-0 grid size-11 place-items-center rounded-bl-lg bg-sheet/90 text-ink-2 hover:text-danger focus-visible:outline-2";

  return (
    <fieldset
      aria-describedby={`${id}-note`}
      onDragOver={(e) => {
        e.preventDefault();
        if (!locked) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (!locked) void take([...(e.dataTransfer.files ?? [])]);
      }}
      className={`min-w-0 rounded-xl border-[1.5px] border-dashed p-3 transition-colors ${over ? "border-sage-deep bg-mint" : "border-rule-strong"}`}
    >
      <legend className="px-1 text-sm font-medium text-ink">
        {label.replace(/ \(optional\)$/, "")}
        {label.endsWith("(optional)") && <span className="font-normal text-ink-3"> (optional)</span>}
      </legend>

      {(kept.length > 0 || held.length > 0 || sending > 0) && (
        <ul className="mb-3 flex flex-wrap gap-2" aria-label="Photos">
          {kept.map((p, i) => (
            <li key={p.id} className={tile}>
              <a href={p.href} target="_blank" rel="noreferrer" className="block size-full" title="Open full size">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p.href} alt={`Photo ${i + 1}${p.takenBy ? `, by ${p.takenBy.name}` : ""}`} className="size-full object-cover" loading="lazy" />
              </a>
              {remove && p.canRemove !== false && !disabled && (
                <button suppressHydrationWarning type="button" className={removeButton} onClick={() => void drop(p)} aria-label={`Remove photo ${i + 1}`}>
                  <Trash2 className="size-4" aria-hidden />
                </button>
              )}
            </li>
          ))}
          {held.map((h, i) => (
            <li key={h.url} className={tile}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={h.url} alt={`New photo ${i + 1}`} className="size-full object-cover" />
              {!disabled && (
                <button suppressHydrationWarning type="button" className={removeButton} onClick={() => unhold(i)} aria-label={`Remove new photo ${i + 1}`}>
                  <Trash2 className="size-4" aria-hidden />
                </button>
              )}
            </li>
          ))}
          {Array.from({ length: sending }, (_, i) => (
            <li key={`sending-${i}`} className={`${tile} grid place-items-center`} role="status" aria-label="Sending a photo">
              <Spinner />
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button size="lg" icon={<Camera className="size-4" aria-hidden />} disabled={locked} onClick={() => camera.current?.click()}>
          Take photo
        </Button>
        <Button size="lg" icon={<ImagePlus className="size-4" aria-hidden />} disabled={locked} onClick={() => picker.current?.click()}>
          Upload
        </Button>
        <p id={`${id}-note`} className="text-meta text-ink-3">
          {room === 0 ? `${max} photos is the most here.` : `Or drop pictures here. Up to ${max}.`}
        </p>
      </div>
      <input suppressHydrationWarning ref={camera} type="file" accept="image/*" capture="environment" className="sr-only" tabIndex={-1} aria-hidden
        onChange={(e) => {
          void take([...(e.target.files ?? [])]);
          e.target.value = "";
        }} />
      <input suppressHydrationWarning ref={picker} type="file" accept="image/jpeg,image/png,image/webp,image/*" multiple className="sr-only" tabIndex={-1} aria-hidden
        onChange={(e) => {
          void take([...(e.target.files ?? [])]);
          e.target.value = "";
        }} />
      {problem && (
        <p className="mt-2 text-meta text-danger" role="alert">
          {problem}
        </p>
      )}
    </fieldset>
  );
}
