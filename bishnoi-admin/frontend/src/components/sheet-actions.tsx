import { Download, Upload } from "lucide-react";
import { buttonClass, LinkButton } from "@/src/platform/ui/button";

/** Downloads a list as an Excel report. A plain link: the file comes from a
 *  route handler, so nothing should prefetch it. */
export function ExportButton({ kind, label = "Export" }: { kind: string; label?: string }) {
  return (
    <a href={`/files/report/${kind}`} download className={buttonClass("default", "md")} title="Download as an Excel file">
      <Download className="size-4" aria-hidden />
      {label}
    </a>
  );
}

/** Opens the import page for a list. */
export function ImportButton({ href }: { href: string }) {
  return (
    <LinkButton href={href} icon={<Upload className="size-4" aria-hidden />} title="Add or update records from an Excel or CSV file">
      Import
    </LinkButton>
  );
}
