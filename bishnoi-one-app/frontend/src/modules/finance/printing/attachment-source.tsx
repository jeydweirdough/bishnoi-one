import type { BillFile } from "../payables/types";

/** Metadata only: files are read through their existing permission-checked routes. */
export function PrintAttachmentSources({ files, openBase }: { files: BillFile[]; openBase: string }) {
  return <span hidden>{files.map(file => <span key={file.id}
    data-finance-attachment-url={`${openBase}/${file.id}`}
    data-finance-attachment-name={file.name}
    data-finance-attachment-type={file.contentType} />)}</span>;
}
