import type { Distribution, MaterialStatus, Production, Review } from "@/src/modules/admin/actions/materials";

type Tone = "outline" | "good" | "warn" | "bad" | "info" | "mute";

// The words and colours each state shows, once, for the list and the record.

export const MATERIAL_STATUS: Record<MaterialStatus, { text: string; tone: Tone }> = {
  draft: { text: "Draft", tone: "outline" },
  pharmacy_review: { text: "For pharmacy review", tone: "info" },
  returned: { text: "Returned for changes", tone: "warn" },
  rejected: { text: "Rejected", tone: "bad" },
  approved: { text: "Approved, to produce", tone: "good" },
  in_production: { text: "In production", tone: "info" },
  available: { text: "In stock", tone: "good" },
  retired: { text: "Retired", tone: "mute" },
};

export const REVIEW: Record<Review, { text: string; tone: Tone }> = {
  draft: { text: "Not submitted", tone: "outline" },
  waiting: { text: "For review", tone: "info" },
  approved: { text: "Approved", tone: "good" },
  returned: { text: "Returned", tone: "warn" },
  rejected: { text: "Rejected", tone: "bad" },
};

export const PRODUCTION: Record<Production["status"], { text: string; tone: Tone }> = {
  ordered: { text: "Ordered", tone: "info" },
  received: { text: "Received", tone: "good" },
  cancelled: { text: "Cancelled", tone: "mute" },
};

export const DISTRIBUTION: Record<Distribution["status"], { text: string; tone: Tone }> = {
  for_approval: { text: "For approval", tone: "info" },
  approved: { text: "Approved", tone: "good" },
  rejected: { text: "Rejected", tone: "bad" },
  distributed: { text: "Distributed", tone: "outline" },
  cancelled: { text: "Cancelled", tone: "mute" },
};
