import type { Tone } from "@/src/platform/ui/figures";
import type { CreditStatus } from "@/src/platform/lib/types";

/** How a credit status reads as a pill: good standing green, approaching due amber, overdue and suspended red. */
export const CREDIT_TONES: Record<CreditStatus, Exclude<Tone, "ink">> = { good: "good", approaching: "warn", overdue: "bad", suspended: "bad" };
