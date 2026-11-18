import type { PackagingRow } from "@/src/modules/inventory/lib/types";

// Quantities in an item's packs (steps 14e and 4A), for server pages and client forms alike: no "use client" here,
// so a server page can call it (it once lived in components/packagings.tsx, a client file, and the item page failed).

/** Box → Boxes, Strip → Strips (as app/packs.py on the server). */
export function plural(name: string, n: number): string {
  if (n === 1 || !name) return name;
  const low = name.toLowerCase();
  if (/(s|x|z|ch|sh)$/.test(low)) return `${name}es`;
  if (/[^aeiou]y$/.test(low)) return `${name.slice(0, -1)}ies`;
  return `${name}s`;
}

/** A quantity in the base unit, written in packs too: 1,050 → "10 Box + 5 Strip" (biggest first). */
export function inPacks(quantity: number, packs: PackagingRow[], unit: string): string | null {
  if (!packs.length || quantity <= 0) return null;
  let left = quantity;
  const parts: string[] = [];
  for (const p of [...packs].sort((a, b) => b.quantity - a.quantity)) {
    const n = Math.floor(left / p.quantity);
    if (n > 0) {
      parts.push(`${n.toLocaleString()} ${plural(p.name, n)}`);
      left -= n * p.quantity;
    }
  }
  if (!parts.length) return null;
  if (left > 0) parts.push(`${left.toLocaleString()} ${plural(unit, left)}`);
  return parts.join(" + ");
}

