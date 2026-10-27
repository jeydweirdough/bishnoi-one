const prepared = new WeakMap<HTMLElement, { fingerprint: string; urls: string[] }>();

function sources(root: HTMLElement) {
  return [...new Map(Array.from(root.querySelectorAll<HTMLElement>("[data-finance-attachment-url]"))
    .map(node => [node.dataset.financeAttachmentUrl!, { url: node.dataset.financeAttachmentUrl!, name: node.dataset.financeAttachmentName || "Attachment" }])).values()];
}
export function attachmentsReady(root: HTMLElement) {
  return !sources(root).length || prepared.get(root)?.fingerprint === JSON.stringify(sources(root));
}
export function clearPrintAttachments(root: HTMLElement) {
  prepared.get(root)?.urls.forEach(url => URL.revokeObjectURL(url));
  prepared.delete(root);
  root.querySelector(".finance-print-attachments")?.replaceChildren();
}

/** Render all evidence before opening print; never silently omit failed pages. */
export async function preparePrintAttachments(root: HTMLElement) {
  if (attachmentsReady(root)) return;
  clearPrintAttachments(root);
  const files = sources(root);
  const fragment = document.createDocumentFragment();
  const urls: string[] = [];
  let count = 0;
  const addPage = (blob: Blob, name: string, width: number, height: number) => {
    if (++count > 100) throw new Error("This print packet exceeds 100 attachment pages. Print the original attachments separately.");
    const url = URL.createObjectURL(blob); urls.push(url);
    const page = document.createElement("section");
    page.className = "finance-print-attachment-page";
    page.dataset.orientation = width > height ? "landscape" : "portrait";
    const caption = document.createElement("p"); caption.textContent = name;
    const image = document.createElement("img"); image.src = url; image.alt = name;
    page.append(caption, image); fragment.append(page);
  };
  let current = "Attachment";
  try {
    for (const file of files) {
      current = file.name;
      const url = new URL(file.url, window.location.origin);
      if (url.origin !== window.location.origin) throw new Error("Unsupported attachment address.");
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(30000) });
      if (!response.ok) throw new Error("The file could not be read with your current access.");
      const blob = await response.blob();
      if (blob.type.split(";")[0] === "application/pdf") {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/finance/pdfjs/pdf.worker.min.mjs";
        const task = pdfjs.getDocument({ data: new Uint8Array(await blob.arrayBuffer()),
          cMapUrl: "/finance/pdfjs/cmaps/", cMapPacked: true, standardFontDataUrl: "/finance/pdfjs/standard_fonts/",
          wasmUrl: "/finance/pdfjs/wasm/", iccUrl: "/finance/pdfjs/iccs/", enableXfa: false });
        try {
          const pdf = await task.promise;
          if (count + pdf.numPages > 100) throw new Error("This print packet exceeds 100 attachment pages.");
          for (let number = 1; number <= pdf.numPages; number++) {
            const page = await pdf.getPage(number);
            const base = page.getViewport({ scale: 1 });
            const scale = Math.min(150 / 72, Math.sqrt(16000000 / (base.width * base.height)));
            const viewport = page.getViewport({ scale });
            const canvas = document.createElement("canvas");
            canvas.width = Math.ceil(viewport.width); canvas.height = Math.ceil(viewport.height);
            await page.render({ canvas, viewport, background: "white" }).promise;
            const image = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error("Page could not be rendered.")), "image/png"));
            addPage(image, `${file.name} — page ${number} of ${pdf.numPages}`, viewport.width, viewport.height);
            canvas.width = 0; canvas.height = 0; page.cleanup();
          }
        } finally { await task.destroy(); }
      } else if (/^image\/(png|jpeg|webp)$/.test(blob.type)) {
        const bitmap = await createImageBitmap(blob);
        addPage(blob, file.name, bitmap.width, bitmap.height); bitmap.close();
      } else throw new Error("This file format cannot be included. Download and print the original separately.");
    }
    root.querySelector(".finance-print-attachments")!.replaceChildren(fragment);
    prepared.set(root, { fingerprint: JSON.stringify(files), urls });
  } catch (error) {
    urls.forEach(url => URL.revokeObjectURL(url));
    throw new Error(`${current}: ${error instanceof Error ? error.message : "Unable to prepare attachment."}`);
  }
}
