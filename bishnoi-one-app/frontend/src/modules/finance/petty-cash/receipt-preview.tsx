import { FileText } from "lucide-react";
import { receiptUrl, showsInline, type ReceiptFile } from "@/src/modules/finance/petty-cash/types";

const size = (bytes: number) => (bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`);

/**
 * One receipt, shown beside its line so whoever checks it reads both at once: a photo drawn in
 * place, a PDF in a frame (both open full size in a new tab). A photo the browser can't draw
 * (HEIC) is a link. On paper, every receipt prints after the voucher instead (printing/attachments.ts).
 */
export function ReceiptPreview({ voucherId, lineId, file }: { voucherId: string; lineId: string; file: ReceiptFile }) {
  const url = receiptUrl(voucherId, lineId);
  return (
    <div className="space-y-1.5 print:hidden">
      {showsInline(file.contentType) ? (
        <a href={url} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-[3px] border border-rule bg-bench" title="Open the receipt full size">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt={`Receipt: ${file.name}`} className="mx-auto max-h-80 w-auto object-contain" />
        </a>
      ) : file.contentType === "application/pdf" ? (
        <iframe src={url} title={`Receipt: ${file.name}`} className="h-80 w-full rounded-[3px] border border-rule bg-bench" />
      ) : (
        <p className="rounded-[3px] border border-rule bg-bench px-3 py-4 text-sm text-ink-2">This kind of photo can&apos;t be shown here. Open it to see the receipt.</p>
      )}
      <p className="flex items-center gap-1.5 text-meta text-ink-3">
        <FileText className="size-3.5 shrink-0" aria-hidden />
        <a href={url} target="_blank" rel="noreferrer" className="min-w-0 truncate font-medium text-hema hover:underline">
          {file.name}
        </a>
        <span className="shrink-0">
          · {size(file.size)} · {file.uploadedBy}
        </span>
      </p>
    </div>
  );
}
