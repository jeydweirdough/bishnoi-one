"use client";

import { Trash2, Upload, X } from "lucide-react";
import { useId, useRef, useState, type ChangeEvent, type Ref } from "react";

// Every file the apps take, one way: a dashed box to drop it on (or browse),
// what it may be under that, then the file chosen, as a row with its type,
// name and size, removable; a bar while it uploads.

type Props = {
  /** What the input accepts: ".xlsx,.csv" or "image/png,image/jpeg". */
  accept?: string;
  /** The line under "Drop your file here": what it may be. "PDF, JPG or PNG, up to 8 MB". */
  note?: string;
  /** Larger files are refused here, before they're sent. */
  maxBytes?: number;
  /** For a form read with FormData: the file goes with it under this name. */
  name?: string;
  id?: string;
  /** The input itself, for a form that reads its files. */
  ref?: Ref<HTMLInputElement>;
  /** Called with the file chosen (or dropped); null when it's removed. */
  onFile?: (file: File | null) => void;
  /** The input's own change, for a form that submits when a file is picked. */
  onChange?: (e: ChangeEvent<HTMLInputElement>) => void;
  /** It's being uploaded: a bar on the row, and nothing can be changed. */
  busy?: boolean;
  /** The file already kept (a template's form, a material's file), shown until another is chosen. */
  current?: { name: string; size?: number | null } | null;
  /** Rows show the file but can't take it away (the upload happens as soon as it's picked). */
  keep?: boolean;
  disabled?: boolean;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
};

export function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(bytes < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

const typeOf = (name: string) => (name.includes(".") ? name.split(".").pop()!.slice(0, 4).toUpperCase() : "FILE");

export function FileDrop({ accept, note, maxBytes, name, id, ref, onFile, onChange, busy = false, current = null, keep = false, disabled = false, ...aria }: Props) {
  const inner = useRef<HTMLInputElement | null>(null);
  const fallbackId = useId();
  const inputId = id ?? fallbackId;
  const [file, setFile] = useState<File | null>(null);
  const [over, setOver] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const locked = disabled || busy;

  function setInput(el: HTMLInputElement | null) {
    inner.current = el;
    if (typeof ref === "function") ref(el);
    else if (ref) (ref as { current: HTMLInputElement | null }).current = el;
  }

  function accepts(f: File) {
    if (!accept) return true;
    const ext = `.${f.name.split(".").pop()?.toLowerCase()}`;
    return accept.split(",").some((a) => {
      const t = a.trim().toLowerCase();
      return t === ext || t === f.type || (t.endsWith("/*") && f.type.startsWith(t.slice(0, -1)));
    });
  }

  function take(f: File | null, fromDrop = false) {
    setRefused(null);
    if (f && !accepts(f)) return setRefused(`${f.name} isn't a kind of file this takes.`);
    if (f && maxBytes && f.size > maxBytes) return setRefused(`${f.name} is ${size(f.size)}: the maximum is ${size(maxBytes)}.`);
    setFile(f);
    const input = inner.current;
    if (fromDrop && input && f) {
      // A dropped file goes into the input too, so the form sends it like a picked one.
      const dt = new DataTransfer();
      dt.items.add(f);
      input.files = dt.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
    onFile?.(f);
  }

  function remove() {
    if (inner.current) inner.current.value = "";
    setFile(null);
    onFile?.(null);
  }

  const shown = file ? { name: file.name, size: file.size } : current;

  return (
    <div>
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault();
          if (!locked) setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          if (!locked) take(e.dataTransfer.files?.[0] ?? null, true);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-[18px] border-[1.5px] border-dashed px-6 py-8 text-center transition-colors ${
          over ? "border-sage-deep bg-mint" : "border-rule-strong bg-bench hover:border-ink-3"
        } ${locked ? "pointer-events-none opacity-60" : ""}`}
      >
        <span className="grid size-10 place-items-center rounded-[12px] border border-rule bg-sheet text-ink shadow-sm" aria-hidden>
          <Upload className="size-4.5" />
        </span>
        <span className="mt-3 text-sm text-ink">
          Drop your file here or <span className="font-medium underline underline-offset-2">browse</span>
        </span>
        {note && <span className="mt-1 text-meta text-ink-3">{note}</span>}
        <input
          ref={setInput}
          id={inputId}
          name={name}
          type="file"
          accept={accept}
          disabled={locked}
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            if (f && !accepts(f)) {
              e.target.value = "";
              return setRefused(`${f.name} isn't a kind of file this takes.`);
            }
            if (f && maxBytes && f.size > maxBytes) {
              e.target.value = "";
              return setRefused(`${f.name} is ${size(f.size)}: the maximum is ${size(maxBytes)}.`);
            }
            setRefused(null);
            setFile(f);
            onFile?.(f);
            onChange?.(e);
          }}
          {...aria}
        />
      </label>
      {refused && (
        <p className="mt-2 text-meta text-danger" role="alert">
          {refused}
        </p>
      )}

      {shown && (
        <div className="mt-4">
          <p className="mb-2 text-sm font-medium text-ink">{file ? (busy ? "Uploading" : "Selected") : "Current file"}</p>
          <div className="rounded-[14px] border border-rule bg-sheet px-3 py-2.5">
            <div className="flex items-center gap-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-[10px] border border-rule bg-bench text-[0.6875rem] font-semibold text-ink-3" aria-hidden>
                {typeOf(shown.name)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-ink">{shown.name}</span>
                {shown.size ? <span className="block text-meta text-ink-3">{size(shown.size)}</span> : null}
              </span>
              {file && !keep && (
                <button
                  type="button"
                  onClick={remove}
                  disabled={busy}
                  className="grid size-8 place-items-center rounded-full text-ink-2 hover:bg-bench hover:text-ink disabled:opacity-40"
                  aria-label={busy ? `Stop ${shown.name}` : `Remove ${shown.name}`}
                >
                  {busy ? <X className="size-4" aria-hidden /> : <Trash2 className="size-4" aria-hidden />}
                </button>
              )}
            </div>
            {busy && (
              <span className="mt-2 block h-1 overflow-hidden rounded-full bg-mint-2" role="progressbar" aria-label={`Uploading ${shown.name}`}>
                <span className="block h-full w-1/3 animate-[file-drop_1.2s_ease-in-out_infinite] rounded-full bg-ink" />
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
