import Link from "next/link";
import { APP_NAME } from "@/src/platform/lib/labels";

/** The brand: the mark and "Bishnoi One", linking home. */
export function Brand({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-2.5">
      <img src="/brand/bishnoi-one-mark.png" alt="" width={36} height={36} className="size-9 shrink-0" />
      <span className="text-[1.0625rem] font-semibold tracking-[-0.01em] text-ink">{APP_NAME}</span>
    </Link>
  );
}
