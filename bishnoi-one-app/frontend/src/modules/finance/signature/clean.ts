// Cleaning a signature in the browser (decided 2026-10-22: Plans/Plan - E-signatures):
// the paper made transparent, the ink made black, trimmed and resized. The raw photo
// never leaves the person's computer; only the cleaned PNG is sent.
//
// - A picture that's already transparent: only trimmed and resized; its ink made black.
// - A photo of a signature on white paper: each part of the paper is compared with how
//   bright the paper is around it (so shadows and uneven light don't count as ink);
//   clearly darker is ink. `strength` (0 keeps more, 1 cleaner) sets how much darker.

export type Cleaned = { dataUrl: string; width: number; height: number; empty: boolean; wasTransparent: boolean };

const WORK_MAX = 1600; // longest side while cleaning
const OUT_W = 900;
const OUT_H = 300;
const MAX_CHARS = 380_000; // the API takes up to 300 KB of PNG
const CELL = 24; // paper brightness is estimated per cell of this many pixels

export function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => (URL.revokeObjectURL(url), resolve(img));
    img.onerror = () => (URL.revokeObjectURL(url), reject(new Error("That file couldn't be opened as a picture.")));
    img.src = url;
  });
}

function canvas(w: number, h: number) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return c;
}

/** Whether a fair part of the picture is see-through already. */
export function isTransparent(d: Uint8ClampedArray): boolean {
  let clear = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] < 250) clear++;
  return clear > d.length / 4 / 50;
}

/** The ink as black with its own opacity (alpha), from a photo on paper. */
type Pixels = Uint8ClampedArray<ArrayBuffer>;

export function inkFromPaper(d: Uint8ClampedArray, w: number, h: number, strength: number): Pixels {
  const lum = new Float32Array(w * h);
  for (let p = 0, i = 0; p < lum.length; p++, i += 4) lum[p] = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
  // The paper's brightness around each point: the brightest of each cell, smoothed with its neighbours.
  const cw = Math.ceil(w / CELL), ch = Math.ceil(h / CELL);
  const cells = new Float32Array(cw * ch);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const c = ((y / CELL) | 0) * cw + ((x / CELL) | 0);
    if (lum[y * w + x] > cells[c]) cells[c] = lum[y * w + x];
  }
  const paper = new Float32Array(cw * ch);
  for (let cy = 0; cy < ch; cy++) for (let cx = 0; cx < cw; cx++) {
    let best = 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const x = cx + dx, y = cy + dy;
      if (x >= 0 && y >= 0 && x < cw && y < ch) best = Math.max(best, cells[y * cw + x]);
    }
    paper[cy * cw + cx] = Math.max(best, 40);
  }
  const threshold = 0.1 + 0.25 * strength; // how much darker than the paper counts as ink
  const out = new Uint8ClampedArray(d.length);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const p = y * w + x;
    const darker = (paper[((y / CELL) | 0) * cw + ((x / CELL) | 0)] - lum[p]) / paper[((y / CELL) | 0) * cw + ((x / CELL) | 0)];
    const a = Math.max(0, Math.min(1, (darker - threshold) / 0.18));
    out[p * 4 + 3] = Math.round(a * 255); // black ink: red, green, blue stay 0
  }
  return out;
}

/** Black ink keeping the picture's own transparency. */
function inkFromTransparent(d: Uint8ClampedArray): Pixels {
  const out = new Uint8ClampedArray(d.length);
  for (let i = 0; i < d.length; i += 4) out[i + 3] = d[i + 3];
  return out;
}

/** The smallest box around the ink, with a little margin. */
export function inkBox(d: Uint8ClampedArray, w: number, h: number) {
  let x0 = w, y0 = h, x1 = -1, y1 = -1;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (d[(y * w + x) * 4 + 3] > 40) {
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
    }
  }
  if (x1 < 0) return null;
  const pad = 8;
  return { x: Math.max(0, x0 - pad), y: Math.max(0, y0 - pad), w: Math.min(w, x1 + pad + 1) - Math.max(0, x0 - pad), h: Math.min(h, y1 + pad + 1) - Math.max(0, y0 - pad) };
}

/** A picture (photo, scan, transparent PNG, or the drawing pad) as a clean black signature. */
export function cleanSignature(source: CanvasImageSource & { width: number; height: number }, strength = 0.5): Cleaned {
  const scale = Math.min(1, WORK_MAX / Math.max(source.width, source.height));
  const w = Math.max(1, Math.round(source.width * scale)), h = Math.max(1, Math.round(source.height * scale));
  const work = canvas(w, h);
  const ctx = work.getContext("2d", { willReadFrequently: true })!;
  ctx.drawImage(source, 0, 0, w, h);
  const data = ctx.getImageData(0, 0, w, h);
  const wasTransparent = isTransparent(data.data);
  const ink = wasTransparent ? inkFromTransparent(data.data) : inkFromPaper(data.data, w, h, strength);
  const box = inkBox(ink, w, h);
  if (!box) return { dataUrl: "", width: 0, height: 0, empty: true, wasTransparent };
  ctx.putImageData(new ImageData(ink, w, h), 0, 0);
  let fit = Math.min(1, OUT_W / box.w, OUT_H / box.h);
  for (;;) {
    const out = canvas(Math.max(10, Math.round(box.w * fit)), Math.max(10, Math.round(box.h * fit)));
    out.getContext("2d")!.drawImage(work, box.x, box.y, box.w, box.h, 0, 0, out.width, out.height);
    const dataUrl = out.toDataURL("image/png");
    if (dataUrl.length <= MAX_CHARS || fit < 0.2) return { dataUrl, width: out.width, height: out.height, empty: false, wasTransparent };
    fit *= 0.75;
  }
}
