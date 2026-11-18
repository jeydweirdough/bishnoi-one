import "server-only";
import { accountSend } from "@/src/platform/lib/account";
import type { Slip, SlipBrief } from "./types";

/** A record's approval slip (its latest) and the ones before it; null when there is none or the Platform can't be reached. */
export async function loadRecordSlip(app: string, kind: string, id: string): Promise<{ slip: Slip | null; earlier: SlipBrief[] } | null> {
  try {
    return await accountSend("GET", `/identity/approvals/for?app=${encodeURIComponent(app)}&kind=${encodeURIComponent(kind)}&id=${encodeURIComponent(id)}`);
  } catch {
    return null;
  }
}
