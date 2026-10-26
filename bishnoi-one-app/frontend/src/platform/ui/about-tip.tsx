import { Info } from "lucide-react";
import { Children, type ReactNode } from "react";
import { Tip } from "./tip";

// A page's explanation, kept out of the way (decided 2026-10-25): a header line that is only
// words ("Business expected from customers: how much, by when, and how likely.") becomes an ⓘ
// beside the title with the words on hover, so a page opens on its work, not on reading. A line
// that shows something live (a count that loads, a link, the customer it's for) stays in view.

/** The text of children that are only words and numbers; null when anything else is in them. */
export function plainText(node: ReactNode): string | null {
  const parts: string[] = [];
  let words = true;
  Children.forEach(node, (c) => {
    if (typeof c === "string" || typeof c === "number") parts.push(String(c));
    else if (c !== null && c !== undefined && typeof c !== "boolean") words = false;
  });
  if (!words) return null;
  const text = parts.join("").replace(/\s+/g, " ").trim();
  return text || null;
}

/** The ⓘ beside a page title, when its explanation is only words. */
export function AboutTip({ children }: { children?: ReactNode }) {
  const text = plainText(children);
  if (!text) return null;
  return (
    <Tip tip={text} className="inline-flex text-ink-3 hover:text-ink">
      <Info className="size-[1.125rem]" aria-hidden />
    </Tip>
  );
}
