import { Download } from "lucide-react";
import { buttonClass } from "@/src/modules/finance/platform/ui/button";

/** Downloads what the page shows as a spreadsheet, through one of the export routes (src/exports/download.ts). */
export function DownloadLink({ href }: { href: string }) {
  return (
    <a href={href} download className={buttonClass("default", "sm")}>
      <Download className="size-3.5" aria-hidden />
      Download CSV
    </a>
  );
}
