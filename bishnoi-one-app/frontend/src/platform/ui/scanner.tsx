"use client";

import { Camera, CameraOff, ScanLine } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/src/platform/ui/button";

// Barcode and QR scanning (feature plan step 14c), one box for every screen that scans: a handheld scanner
// (USB or Bluetooth) types the code and presses Enter into the box, which keeps the focus; or the device's
// camera reads it, where the browser can (Chrome on Android and most phones' browsers; not every desktop).
// Fix scanning here, not in a screen.

type Detected = { rawValue: string };
type Detector = { detect: (source: CanvasImageSource) => Promise<Detected[]> };
type DetectorClass = { new (options?: { formats?: string[] }): Detector; getSupportedFormats?: () => Promise<string[]> };

const FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "code_93", "itf", "codabar", "qr_code", "data_matrix"];

function detectorClass(): DetectorClass | null {
  return typeof window !== "undefined" && "BarcodeDetector" in window ? ((window as unknown as { BarcodeDetector: DetectorClass }).BarcodeDetector) : null;
}

/** Calls `onCode` once per code read; the same code read again within a second (a camera sees it many times) counts once. */
export function Scanner({ onCode, busy = false, label = "Scan or type a code", autoFocus = true }: {
  onCode: (code: string) => void | Promise<void>;
  busy?: boolean;
  label?: string;
  autoFocus?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const last = useRef<{ code: string; at: number }>({ code: "", at: 0 });
  const [value, setValue] = useState("");
  const [camera, setCamera] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [canCamera, setCanCamera] = useState(false);

  useEffect(() => setCanCamera(detectorClass() !== null && !!navigator.mediaDevices?.getUserMedia), []);

  const take = useCallback(
    (raw: string) => {
      const code = raw.trim();
      if (!code) return;
      const now = Date.now();
      if (code === last.current.code && now - last.current.at < 1000) return;
      last.current = { code, at: now };
      void onCode(code);
    },
    [onCode],
  );

  useEffect(() => {
    if (!camera) return;
    const Klass = detectorClass();
    if (!Klass || !video.current) return;
    let stream: MediaStream | null = null;
    let stopped = false;
    const detector = new Klass({ formats: FORMATS });
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (stopped || !video.current) return;
        video.current.srcObject = stream;
        await video.current.play();
        const tick = async () => {
          if (stopped || !video.current) return;
          try {
            const found = await detector.detect(video.current);
            if (found[0]?.rawValue) take(found[0].rawValue);
          } catch {
            /* a frame it couldn't read: try the next */
          }
          setTimeout(tick, 250);
        };
        void tick();
      } catch {
        setProblem("The camera couldn't be opened. Allow camera access, or use a scanner.");
        setCamera(false);
      }
    })();
    return () => {
      stopped = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [camera, take]);

  return (
    <div>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          take(value);
          setValue("");
          input.current?.focus();
        }}
        className="flex flex-wrap items-center gap-2"
      >
        <label className="flex h-11 min-w-0 flex-1 items-center gap-2 rounded-lg border border-rule-strong bg-white px-3 focus-within:border-hema">
          <ScanLine className="size-5 shrink-0 text-ink-3" aria-hidden />
          <span className="sr-only">{label}</span>
          <input
            suppressHydrationWarning
            ref={input}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={label}
            autoFocus={autoFocus}
            autoComplete="off"
            spellCheck={false}
            inputMode="text"
            disabled={busy}
            className="min-w-0 flex-1 bg-transparent text-base outline-none"
          />
        </label>
        {canCamera && (
          <Button type="button" icon={camera ? <CameraOff className="size-4" aria-hidden /> : <Camera className="size-4" aria-hidden />} onClick={() => (setProblem(null), setCamera((c) => !c))}>
            {camera ? "Stop camera" : "Use camera"}
          </Button>
        )}
      </form>
      {camera && (
        <video ref={video} muted playsInline className="mt-2 aspect-video w-full max-w-md rounded-lg bg-black object-cover" aria-label="Camera: point it at the barcode" />
      )}
      {problem && <p className="mt-1 text-meta text-danger">{problem}</p>}
    </div>
  );
}
