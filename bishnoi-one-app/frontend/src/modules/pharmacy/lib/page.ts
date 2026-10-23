import "server-only";
import { can } from "@/src/modules/pharmacy/platform/lib/access";
import { getCompanyMe } from "@/src/modules/pharmacy/platform/lib/api";
import { makeFormat } from "@/src/modules/pharmacy/platform/lib/format";

/**
 * What every Pharmacy screen starts with: who is looking, how the company
 * writes money and dates, and whether their role opens this page at all.
 * The API checks each permission again on every call; this only decides
 * what to offer.
 */
export async function pageFor(permission: string) {
  const me = await getCompanyMe();
  return {
    me,
    fmt: makeFormat(me.org),
    allowed: can(me, permission),
    may: (p: string) => can(me, p),
  };
}

export type Search = Promise<Record<string, string | string[] | undefined>>;

/** One query-string value, or the fallback. */
export function param(search: Record<string, string | string[] | undefined>, key: string, fallback = ""): string {
  const v = search[key];
  return typeof v === "string" ? v.trim() : fallback;
}
