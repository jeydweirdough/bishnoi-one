// A photo of a supplier's invoice, made smaller in the browser before it's sent: phone
// photos run 3–8 MB, and a bill keeps files up to 3 MB each (app/routers/payables.py).
// The longest side becomes 2000 px at most, saved as JPEG, which keeps print readable.
// A PDF, or a photo the browser can't draw (HEIC outside Safari), is sent as it is.

export const MAX_FILE_BYTES = 3 * 1024 * 1024;
export const ACCEPTED = "image/jpeg,image/png,image/webp,image/heic,application/pdf";
const LONGEST = 2000;

export async function shrink(file: File): Promise<File> {
  if (!file.type.startsWith("image/") || file.type === "image/heic") return file;
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return file;
  }
  const scale = Math.min(1, LONGEST / Math.max(bitmap.width, bitmap.height));
  if (scale === 1 && file.size <= MAX_FILE_BYTES) {
    bitmap.close();
    return file;
  }
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) return file;
  ctx.fillStyle = "#fff"; // a transparent PNG gets a white page, not a black one
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const blob = await new Promise<Blob | null>((done) => canvas.toBlob(done, "image/jpeg", 0.85));
  if (!blob) return file;
  return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
}
