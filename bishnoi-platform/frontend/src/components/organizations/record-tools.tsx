import { Pencil } from "lucide-react";
import Link from "next/link";

// Small icon controls that sit beside the name of what they act on: a record
// page's title, or one row of a list. Their tooltip names the target.

const ICON = "inline-flex size-8 shrink-0 items-center justify-center rounded-[3px] text-ink-3 transition-colors";

/** For ConfirmButton's trigger when it is only an icon. */
export const ICON_TRIGGER = "!size-8 !px-0 !text-ink-3 hover:!bg-hema-tint hover:!text-hema";
export const ICON_TRIGGER_DANGER = "!size-8 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger";
export const ICON_BUTTON = `${ICON} hover:bg-hema-tint hover:text-hema`;

export function EditLink({ href, what }: { href: string; what: string }) {
  return (
    <Link href={href} aria-label={`Edit ${what}`} title={`Edit ${what}`} className={ICON_BUTTON}>
      <Pencil className="size-4" aria-hidden />
    </Link>
  );
}

/** "Suspended" beside a name. */
export function SuspendedTag({ label = "Suspended" }: { label?: string }) {
  return (
    <span className="inline-flex h-5 shrink-0 items-center rounded-[2px] border border-ink-2 px-1.5 text-stamp whitespace-nowrap text-ink-2 uppercase">
      {label}
    </span>
  );
}
