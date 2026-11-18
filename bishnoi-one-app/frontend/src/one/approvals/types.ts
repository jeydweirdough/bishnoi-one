// An approval slip (Step 4C) as Bishnoi One Platform sends it (/identity/approvals).

export type SlipStatus = "pending" | "approved" | "returned" | "cancelled";

export type SlipBrief = {
  id: string;
  no: number | null;
  number: string;
  status: SlipStatus;
  statusLabel: string;
  app: string;
  kind: string;
  kindLabel: string;
  record: { id: string; number: string | null; url: string | null };
  title: string;
  summary: {
    customer?: string;
    totalCentavos?: number;
    grossCentavos?: number;
    discountCentavos?: number;
    currency?: string;
    units?: number;
    lines?: { name: string; quantity: number; freeQuantity?: number; soldAs?: string | null; totalCentavos: number }[];
    moreLines?: number;
    warehouse?: string | null;
    scheduledOn?: string | null;
    notes?: string | null;
    salesperson?: string | null;
    quote?: string | null;
  };
  requestedBy: { id: string | null; name: string; email: string | null };
  waitingOn: string | null;
  waitingStep: string | null;
  mine: boolean;
  myTurn: boolean;
  createdAt: string;
  finishedAt: string | null;
  note: string | null;
};

export type SlipStep = {
  id: string;
  position: number;
  label: string;
  status: "waiting" | "signed" | "returned" | "skipped";
  approver: { id: string | null; name: string | null } | null;
  group: { app: string; permission: string } | null;
  note: string | null;
  actedBy: string | null;
  actedAs: "approver" | "holder" | "administrator" | null;
  actedAt: string | null;
  signature: string | null;
  current: boolean;
};

export type SlipAttachment = {
  id: string;
  kind: "record" | "file";
  label: string;
  app: string | null;
  recordKind: string | null;
  recordId: string | null;
  number: string | null;
  url: string | null;
  fileName: string | null;
  contentType: string | null;
  size: number | null;
  addedBy: string;
  addedAt: string;
};

export type Slip = SlipBrief & {
  steps: SlipStep[];
  attachments: SlipAttachment[];
  replaces: { id: string; number: string; status: SlipStatus; note: string | null } | null;
  canSign: boolean;
  actingAs: "approver" | "holder" | "administrator" | null;
  canAddFiles: boolean;
};
