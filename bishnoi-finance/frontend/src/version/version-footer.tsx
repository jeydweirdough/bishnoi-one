import Link from "next/link";
import { SCREENS_BUILD, buildsDiffer } from "./build";
import { VERSION } from "./changes";

/** The bottom of Finance's sidebar: the version, and which code the screens and
 *  the API run, linking to what's new. Collapsed to icons, only the number. */
export function VersionFooter({ apiBuild }: { apiBuild: string | null | undefined }) {
  const differ = buildsDiffer(apiBuild);
  const builds = [SCREENS_BUILD && `Screens ${SCREENS_BUILD}`, apiBuild && `API ${apiBuild}`].filter(Boolean).join(" · ");
  return (
    <Link href="/whats-new" className="block rounded-[3px] px-3 py-2 text-meta text-ink-3 hover:bg-sheet hover:text-ink" title="What's new in Finance">
      <span className="hidden text-center group-data-[rail=true]/side:block">v{VERSION}</span>
      <span className="block group-data-[rail=true]/side:hidden">
        <span className="block font-medium">Version {VERSION} · What&apos;s new</span>
        {builds && <span className="block truncate">{builds}</span>}
        {differ && <span className="block text-danger">The screens and the API are on different builds.</span>}
      </span>
    </Link>
  );
}
