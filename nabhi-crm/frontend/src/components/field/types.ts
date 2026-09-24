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
  owner: { id: string; name: string };
  createdAt: string;
  can: { edit: boolean; delete: boolean };
};

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

export type DoctorBalance = { balance: Owed | null; history: { asOf: string; balanceCentavos: number; note: string | null }[] };

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
