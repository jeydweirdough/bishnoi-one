// The company's org chart, as /identity/organisation gives it (feature plan step 4).

export type UnitKind = "division" | "department" | "team";

export type OrgUnit = {
  id: string;
  kind: UnitKind;
  name: string;
  parentId: string | null;
  managerId: string | null;
  areas: string[];
  isActive: boolean;
  /** Active people whose main unit it is. */
  people: number;
};

export type OrgBranch = { id: string; name: string; address: string | null; isActive: boolean; people: number };

export type OrgPerson = {
  id: string;
  fullName: string;
  email: string;
  title: string | null;
  status: "active" | "suspended";
  mainUnitId: string | null;
  otherUnitIds: string[];
  branchId: string | null;
};

export type OrgData = { units: OrgUnit[]; branches: OrgBranch[]; people: OrgPerson[]; notPlaced: number };

export const KIND_LABEL: Record<UnitKind, string> = { division: "Division", department: "Department", team: "Team" };
