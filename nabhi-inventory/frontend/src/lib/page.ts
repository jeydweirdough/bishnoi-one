import "server-only";
import { getCompanyMe } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";

export type Search = Promise<Record<string, string | string[] | undefined>>;
export type Params<T> = Promise<T>;

/** Who's asking, what they may do, and how their company writes money and dates. */
export async function context() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const may = (permission: string) => me.permissions?.includes(permission) ?? false;
  /** A moment as the company's clocks show it: "24 Sep 2026, 9:42 AM". */
  const stamp = fmt.on({ dateStyle: "medium", timeStyle: "short" });
  return { me, fmt, may, at: (iso: string | null) => (iso ? stamp.format(new Date(iso)) : "—"), day: (key: string | null) => (key ? fmt.dateLabel(key) : "—") };
}
