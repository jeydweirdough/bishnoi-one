"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { moduleOfPath } from "@/src/platform/lib/modules";
import { Dots } from "@/src/platform/ui/dots";

/**
 * Says at once that a click was heard. The moment someone clicks a link to
 * another page of this app (a sidebar row, a tab, a filter), that link lights
 * up and a thin bar runs along the top, until the new page has arrived. The
 * sidebar itself never reloads: only the page beside it does, and
 * app/(app)/loading.tsx fills that in with the page's shape meanwhile.
 *
 * Opening another app (the CRM from Inventory, the Admin Console from Finance) has no shape to show yet:
 * the 4-dot loader says which app is opening (decided 2026-10-30).
 *
 * It listens to clicks on the whole document, so every link in every screen
 * gets this without being changed. The styles are in styles/globals.css
 * ("Navigation under way").
 */
export function NavProgress() {
  const pathname = usePathname();
  const search = useSearchParams();
  const [pending, setPending] = useState(false);
  // The app being opened, when the link leads out of this one.
  const [opening, setOpening] = useState<string | null>(null);
  const clicked = useRef<HTMLAnchorElement | null>(null);

  // Arrived: the address changed, so the page it asked for is here.
  useEffect(() => {
    clicked.current?.removeAttribute("data-nav-pending");
    clicked.current = null;
    setPending(false);
    setOpening(null);
  }, [pathname, search]);

  useEffect(() => {
    let giveUp: ReturnType<typeof setTimeout> | undefined;
    function onClick(e: MouseEvent) {
      // Capture phase: before Next's Link handles the click (and prevents its default).
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const link = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || (link.target && link.target !== "_self") || link.hasAttribute("download")) return;
      const to = new URL(link.href, window.location.href);
      if (to.origin !== window.location.origin) return; // another app: the browser shows its own loading
      if (to.pathname === window.location.pathname && to.search === window.location.search) return; // this page
      clicked.current?.removeAttribute("data-nav-pending");
      link.setAttribute("data-nav-pending", "");
      clicked.current = link;
      setPending(true);
      const there = moduleOfPath(to.pathname);
      setOpening(there && there.key !== moduleOfPath(window.location.pathname)?.key ? there.label : null);
      clearTimeout(giveUp);
      // A navigation that ends where it began (a redirect back) never changes the address.
      giveUp = setTimeout(() => {
        clicked.current?.removeAttribute("data-nav-pending");
        setPending(false);
        setOpening(null);
      }, 15_000);
    }
    document.addEventListener("click", onClick, true);
    return () => {
      document.removeEventListener("click", onClick, true);
      clearTimeout(giveUp);
    };
  }, []);

  if (!pending) return null;
  if (opening) {
    return (
      <div className="dots-overlay">
        <Dots size="lg" label={`Opening ${opening}…`} show />
      </div>
    );
  }
  return (
    <div className="nav-progress" role="status">
      <span className="sr-only">Loading the page…</span>
    </div>
  );
}
