// Field work, as the API answers it (app/routers/field.py).

export type VisitOutcome = "collected" | "promised" | "not_in" | "updated" | "other";

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
