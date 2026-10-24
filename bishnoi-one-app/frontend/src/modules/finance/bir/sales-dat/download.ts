// Saving what the Sales DAT screen makes. Everything is made in the browser, so a
// download is a file handed straight to the browser (as the converter did).

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob), a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  /* keep the file available long enough for a "Save as" dialog or a slow disk */
  setTimeout(() => URL.revokeObjectURL(url), 120000);
}

export const saveText = (text: string, filename: string, type = "application/octet-stream") => saveBlob(new Blob([text], { type }), filename);

/** "010065182S092026.DAT" -> "010065182S092026.csv" (a browser's " (1)" is dropped). */
export const csvName = (datName: string | null | undefined) => String(datName || "sales.DAT").replace(/( \(\d+\))?\.DAT$/i, "") + ".csv";

/** The engine's records are whole centavos; DAT lines are in pesos. */
export const centavos = (pesos: number) => Math.round(pesos * 100);
