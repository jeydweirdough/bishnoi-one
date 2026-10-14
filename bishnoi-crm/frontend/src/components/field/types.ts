// Field work, as the API answers it (app/routers/field.py).

export type VisitOutcome = "detailed" | "collected" | "promised" | "not_in" | "updated" | "other";
/** The doctor's Patient Care Group, on a visit (Rx playbook). */
export type CareGroup = "enrolled" | "followed_up" | "not_now";

export type Visit = {
  id: string;
  company: { id: string; name: string };
  visitedAt: string;
  outcome: VisitOutcome;
  amountCentavos: number;
  receiptNo: string | null;
  notes: string | null;
  /** What was detailed, in order (P6). */
  detailing: Detail[];
  /** What the next visit is for. */
  nextObjective: string | null;
  careGroup: CareGroup | null;
  owner: { id: string; name: string };
  createdAt: string;
  /** Where the phone was when it was logged; null when it didn't say. */
  location: { latitude: number; longitude: number; accuracyM: number | null } | null;
  /** How far that was from the clinic's pin, and whether that's at the clinic. Null: no telling. */
  distanceM: number | null;
  atClinic: boolean | null;
  can: { edit: boolean; delete: boolean };
};

export type Reaction = "will_prescribe" | "already_prescribes" | "interested" | "neutral" | "concerns" | "not_interested";

export type Detail = { productId: string; productName: string; message: string | null; reaction: Reaction };

/** What the visit form needs about a doctor: the last visit's objective, and what can be detailed. */
export type VisitBrief = {
  lastObjective: { text: string; visitedAt: string; by: { id: string; name: string } | null } | null;
  products: { id: string; name: string; strength: string | null }[];
};

export type DetailingSummary = {
  month: string;
  visits: number;
  detailedVisits: number;
  products: { product: { id: string; name: string }; visits: number; doctors: number; reactions: Record<Reaction, number> }[];
};

export type Pin = { latitude: number; longitude: number; pinnedAt: string | null };

/** What a doctor owes now: the newest uploaded balance, less what was collected after its date. */
export type Owed = { asOf: string; balanceCentavos: number; collectedSinceCentavos: number; owedCentavos: number };

export type DoctorRow = {
  id: string;
  name: string;
  city: string | null;
  owner: { id: string; name: string };
  balance: Owed | null;
  lastVisitAt: string | null;
  /** The clinic's pin, if someone set it standing there. */
  pin: Pin | null;
} & DoctorPlan;

/** A doctor's place in the plan (Rx playbook): tier 1–3 (visits a month 4/2/1) and this week's zone. */
export type Zone = "red" | "yellow" | "green";
export type DoctorPlan = { tier: 1 | 2 | 3 | null; zone: Zone | null; zoneSetAt: string | null; careGroupAt: string | null; visitsThisMonth: number; visitsNeeded: number | null };

/** How much of the list a month reached (GET /field/coverage). */
export type Coverage = {
  month: string;
  thisMonth: string;
  doctors: number;
  visited: number;
  coveragePct: number | null;
  goalPct: number;
  tiers: { tier: 1 | 2 | 3; visitsNeeded: number; doctors: number; onPlan: number }[];
  untiered: number;
  zones: Record<Zone | "none", number>;
};

export type Doctors = { items: DoctorRow[]; total: number; owedCentavos: number };

export type DoctorBalance = {
  balance: Owed | null;
  history: { asOf: string; balanceCentavos: number; note: string | null }[];
  pin: Pin | null;
  can: { pin: boolean; unpin: boolean };
};

export type RoutePoint = { latitude: number; longitude: number; accuracyM: number; at: string };

export type RouteDaySummary = { day: string; distanceM: number; points: number; firstAt: string; lastAt: string };

export type Route = {
  person: { id: string; name: string };
  day: string;
  today: string;
  summary: RouteDaySummary | null;
  points: RoutePoint[];
  visits: (Visit & { clinic: Pin | null })[];
  keptDays: number;
  /** The day's plan, each planned doctor visited or not. */
  planned: { id: string; slot: "morning" | "midday" | "afternoon"; doctor: { id: string; name: string; zone: Zone | null; tier: 1 | 2 | 3 | null }; visited: boolean }[];
};

export type RouteDays = { person: { id: string; name: string }; month: string; days: RouteDaySummary[] };

/** The four things a month is measured by. */
export type FieldCounts = { doctorsVisited: number; doctorsUpdated: number; amountCentavos: number; collectionVisits: number };

export type PersonMonth = {
  person: { id: string; name: string };
  team: { id: string; name: string } | null;
  goal: FieldCounts | null;
  actual: FieldCounts;
};

export type Performance = { month: string; thisMonth: string; people: PersonMonth[]; totals: FieldCounts; canSetGoals: boolean };

export type GoalsPayload = { month: string; people: { person: { id: string; name: string }; team: { id: string; name: string } | null; goal: FieldCounts | null }[] };

/** A doctor on a day of the week's plan (GET /field/plan). */
export type PlanSlot = "morning" | "midday" | "afternoon";
export type PlanStop = { id: string; day: string; slot: PlanSlot; doctor: { id: string; name: string; city: string | null; tier: 1 | 2 | 3 | null; zone: Zone | null }; visited: boolean };
export type WeekPlan = {
  person: { id: string; name: string };
  week: string;
  thisWeek: string;
  today: string;
  callsADay: number;
  days: { day: string; stops: PlanStop[] }[];
  status: { sentAt: string | null; changedAt: string | null; reviewedAt: string | null; reviewedBy: { id: string; name: string } | null; note: string | null };
  can: { plan: boolean; review: boolean };
};

/** A government assistance application (PAP, Rx playbook) for a doctor's patient. */
export type AssistanceProgram = "dswd" | "pcso" | "ovp" | "yakap";
export type AssistanceStatus = "pending" | "approved" | "denied";
export type Assistance = {
  id: string;
  program: AssistanceProgram;
  patientName: string;
  doctor: { id: string; name: string };
  /** The GetMeds products it's for, at least one. */
  products: { id: string | null; name: string }[];
  submittedOn: string;
  status: AssistanceStatus;
  decidedOn: string | null;
  receiptNo: string | null;
  notes: string | null;
  /** The patient's IDs and the other documents; opened at /field/assistance/{id}/files/{n}. */
  attachments: { n: number; kind: "id" | "document"; name: string; contentType: string; size: number }[];
  owner: { id: string; name: string };
  updatedAt: string;
};
export type AssistanceList = {
  month: string;
  thisMonth: string;
  items: Assistance[];
  counts: { pending: number; approved: number; denied: number; submitted: number };
  programs: { key: AssistanceProgram; name: string; gives: string; days: string }[];
  products: { id: string; name: string; strength: string | null }[];
  can: { file: boolean; edit: boolean };
};
