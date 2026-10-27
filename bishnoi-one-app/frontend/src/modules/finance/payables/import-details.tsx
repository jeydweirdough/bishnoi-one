import type { ReactNode } from "react";

function values(value: unknown): ReactNode {
  if (value == null) return "Not supplied";
  if (Array.isArray(value)) return <ul className="space-y-1">{value.map((item, index) => <li key={index}>{values(item)}</li>)}</ul>;
  if (typeof value === "object") return <dl className="space-y-1">{Object.entries(value).map(([key, item]) => <div key={key}><dt className="font-medium">{key.replace(/([a-z])([A-Z])/g, "$1 $2").replaceAll("_", " ")}</dt><dd className="whitespace-pre-wrap break-words">{values(item)}</dd></div>)}</dl>;
  return String(value);
}

export function ImportedDetails({ details }: { details: Record<string, unknown> }) {
  if (!details || !Object.keys(details).length) return null;
  return <details className="my-3 text-sm"><summary className="cursor-pointer font-medium">Imported details kept for later</summary><p className="my-2 text-meta text-ink-2">Original source hints and unresolved values. These do not confirm tax registration or withholding.</p>{values(details)}</details>;
}
