"use client";

import { useState, type DragEvent, type ReactNode } from "react";
import { FileInput } from "@/src/platform/ui/field";

/** Files dropped here, or chosen. Nothing is uploaded: they're read in the browser. */
export function Drop({ title, hint, accept, multiple = true, onFiles }: { title: string; hint?: ReactNode; accept: string; multiple?: boolean; onFiles: (files: File[]) => void }) {
  const [over, setOver] = useState(false);
  const stop = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };
  return (
    <div
      onDragEnter={(e) => (stop(e), setOver(true))}
      onDragOver={(e) => (stop(e), setOver(true))}
      onDragLeave={(e) => (stop(e), setOver(false))}
      onDrop={(e) => {
        stop(e);
        setOver(false);
        const files = Array.from(e.dataTransfer.files);
        if (files.length) onFiles(multiple ? files : files.slice(0, 1));
      }}
      className={`rounded-[3px] border-2 border-dashed px-4 py-5 transition-colors ${over ? "border-hema bg-hema-tint" : "border-rule-strong"}`}
    >
      <p className="text-sm font-semibold text-ink">{title}</p>
      {hint && <p className="mt-0.5 text-meta text-ink-3">{hint}</p>}
      <FileInput
        className="mt-3"
        accept={accept}
        multiple={multiple}
        aria-label={title}
        onChange={(e) => {
          const files = Array.from(e.target.files || []);
          e.target.value = ""; /* so choosing the same (edited) file again reloads it */
          if (files.length) onFiles(files);
        }}
      />
    </div>
  );
}
