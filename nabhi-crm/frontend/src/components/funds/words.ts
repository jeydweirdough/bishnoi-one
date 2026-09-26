import type { FundRequest, FundStatus } from "./types";

// How a request's step reads, and how loud: what's waiting on the person
// looking stands out; what's done is quiet.

export type Tone = "waiting" | "you" | "done" | "stopped";

export const TONE_CLASS: Record<Tone, string> = {
  waiting: "bg-hema-tint text-hema",
  you: "bg-[#fdf3e1] text-due-today",
  done: "bg-[#e6f2eb] text-filed",
  stopped: "bg-bench text-ink-3",
};

/** Whose move it is, from where the requester stands. */
export function toneOf(status: FundStatus): Tone {
  if (status === "to_liquidate" || status === "to_return") return "you";
  if (status === "closed") return "done";
  if (status === "declined" || status === "cancelled") return "stopped";
  return "waiting";
}

/** The steps a request goes through, and which one it's at: 0 asked, 1 approved,
 *  2 released, 3 liquidated, 4 settled. An unliquidated one is done on release. */
export function stepsOf(r: FundRequest): { label: string; done: boolean; current: boolean }[] {
  const labels = r.liquidate ? ["Requested", "Approved", "Released", "Liquidated", "Settled"] : ["Requested", "Approved", "Released"];
  const at: Record<FundStatus, number> = {
    pending: 1,
    declined: 1,
    cancelled: 1,
    approved: 2,
    to_release: 2,
    to_liquidate: 3,
    to_check: 4,
    to_return: 4,
    to_reimburse: 4,
    closed: labels.length,
  };
  const reached = at[r.status];
  return labels.map((label, i) => ({ label, done: i < reached, current: i === reached && r.status !== "declined" && r.status !== "cancelled" }));
}

/** What the person looking needs to do next, in a sentence, or null. */
export function nextFor(r: FundRequest, fmt: { peso: (c: number) => string; dateLabel: (d: string) => string }): string | null {
  const f = r.finance;
  switch (r.status) {
    case "pending":
      return r.can.approve ? "For your approval." : "For your Team Lead's approval.";
    case "approved":
      return r.financeError ? `Approved. It will be forwarded to Finance once Finance is reachable (${r.financeError}).` : "Approved and forwarded to Finance.";
    case "to_release":
      return "Approved. For release by Finance.";
    case "to_liquidate":
      return r.can.liquidate
        ? `Add each expense with its official receipt, then submit the liquidation${f?.release?.liquidateBy ? ` on or before ${fmt.dateLabel(f.release.liquidateBy)}` : ""}.`
        : "Released. For liquidation by the requester.";
    case "to_check":
      return "Liquidation under review by Finance.";
    case "to_return":
      return f ? `Refund of ${fmt.peso(f.returnDueCentavos - f.returnedCentavos)} due to Finance.` : "Refund due to Finance.";
    case "to_reimburse":
      return f ? `Reimbursement of ${fmt.peso(f.reimburseDueCentavos - f.reimbursedCentavos)} due to you from Finance.` : "Reimbursement due to you from Finance.";
    default:
      return null;
  }
}
