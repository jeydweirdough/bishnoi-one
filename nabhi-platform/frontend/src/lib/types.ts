// The Platform API's answers (backend/app/routers), camelCase on the wire.
// Moments are ISO strings with their zone.

export type Ref = { id: string; name: string };

export type Health = "operational" | "degraded" | "down" | "maintenance" | "unknown" | "retired";
export type Check = { status: "operational" | "degraded" | "down"; ms: number | null; httpStatus: number | null; detail: string | null; checkedAt: string };

// ---- Organizations ----

export type Company = {
  id: string;
  name: string;
  slug: string;
  status: "active" | "suspended";
  currency: string;
  timezone: string;
  contactEmail: string | null;
  notes: string | null;
  createdAt: string;
  suspendedAt: string | null;
  userCount: number;
  appCount: number;
  openTickets: number;
};

export type Unit = { id: string; kind: "department" | "branch"; name: string; location: string | null; createdAt: string };

export type CompanyDetail = Company & {
  activeUserCount: number;
  applications: { id: string; key: string; name: string; status: Health; userCount: number }[];
  units: Unit[];
  admins: { id: string; name: string; email: string }[];
  activeIncidents: { id: string; number: string; title: string; severity: IncidentSeverity; status: IncidentStatus }[];
};

// ---- Applications ----

export type Application = {
  id: string;
  key: string;
  name: string;
  description: string | null;
  appUrl: string | null;
  healthUrl: string | null;
  version: string | null;
  isActive: boolean;
  status: Health;
  statusOverride: "degraded" | "maintenance" | "outage" | null;
  statusNote: string | null;
  sortOrder: number;
  lastCheck: Check | null;
  createdAt: string;
  uptime?: number | null;
  companyCount?: number;
  userCount?: number;
  openTickets?: number;
  activeIncidents?: number;
};

export type Deployment = {
  id: string;
  applicationId: string;
  applicationName: string | null;
  version: string;
  environment: "production" | "staging" | "development";
  notes: string | null;
  deployedAt: string;
  recordedBy: string;
};

export type Integration = {
  id: string;
  applicationId: string;
  applicationName: string | null;
  name: string;
  target: string | null;
  healthUrl: string | null;
  status: "operational" | "degraded" | "down" | "unknown";
  notes: string | null;
  lastCheck: Check | null;
};

export type ApplicationDetail = Application & {
  uptime: number | null;
  userCount: number;
  companies: { id: string; name: string; status: Company["status"]; userCount: number }[];
  deployments: Deployment[];
  integrations: Integration[];
  history: Check[];
  openTickets: { id: string; number: string; title: string; kind: TicketKind; severity: Severity; status: TicketStatus; createdAt: string }[];
  incidents: { id: string; number: string; title: string; severity: IncidentSeverity; status: IncidentStatus; startedAt: string; resolvedAt: string | null }[];
};

// ---- Users and access ----

export type PlatformUser = {
  id: string;
  fullName: string;
  email: string;
  title: string | null;
  isCompanyAdmin: boolean;
  status: "active" | "suspended";
  companyId: string;
  companyName: string | null;
  companyStatus: Company["status"] | null;
  createdAt: string;
  lastActiveAt: string | null;
  applications?: { applicationId: string; key: string; name: string; role: string | null }[];
};

export type Grant = {
  applicationId: string;
  key: string;
  name: string;
  role: string | null;
  isAppAdmin: boolean;
  grantedAt: string;
  grantedBy: string;
};

export type PlatformUserDetail = Omit<PlatformUser, "applications"> & {
  applications: Grant[];
  canBeGiven: { id: string; key: string; name: string }[];
  requests: { id: string; applicationId: string; applicationName: string; role: string | null; status: RequestStatus; createdAt: string }[];
  tickets: { id: string; number: string; title: string; kind: TicketKind; status: TicketStatus; createdAt: string; isOpen: boolean }[];
  activity: AuditEntry[];
};

export type RequestStatus = "pending" | "approved" | "declined";

export type AccessRequest = {
  id: string;
  user: { id: string; name: string; email: string };
  company: Ref;
  application: Ref;
  role: string | null;
  reason: string | null;
  status: RequestStatus;
  createdAt: string;
  decidedAt: string | null;
  decidedBy: string | null;
  decisionNote: string | null;
  companyHasApp: boolean;
};

export type OrgAccess = {
  applications: { id: string; key: string; name: string }[];
  companies: {
    id: string;
    name: string;
    status: Company["status"];
    admins: Ref[];
    cells: { applicationId: string; enabled: boolean; userCount: number }[];
  }[];
};

export type AppAccess = {
  applications: {
    id: string;
    name: string;
    userCount: number;
    roles: { role: string; userCount: number }[];
    admins: { id: string; name: string; companyName: string }[];
  }[];
};

export type Staff = {
  id: string;
  fullName: string;
  email: string;
  role: "admin" | "member";
  roleName: string;
  isActive: boolean;
  createdAt: string;
  lastSignInAt: string | null;
  activeSessions: number;
};

export type Roles = {
  staffRoles: { role: Staff["role"]; name: string; permissions: { area: string; action: string }[]; holders: Staff[] }[];
  permissions: { area: string; action: string; support: boolean }[];
  levels: { companyAdmins: number; applicationAdmins: number };
};

export type StaffSession = {
  id: string;
  staff: { id: string; name: string; email: string; roleName: string };
  startedAt: string;
  expiresAt: string;
  address: string | null;
  isYours: boolean;
};

// ---- Support ----

export type TicketKind = "complaint" | "bug" | "issue" | "feature" | "support";
export type Severity = "critical" | "high" | "medium" | "low";
export type TicketStatus = "reported" | "triaged" | "assigned" | "investigating" | "fixing" | "testing" | "resolved" | "closed";

export type Ticket = {
  id: string;
  number: string;
  kind: TicketKind;
  title: string;
  description: string | null;
  severity: Severity;
  status: TicketStatus;
  isOpen: boolean;
  company: Ref | null;
  application: Ref | null;
  reporter: { id: string | null; name: string | null; email: string | null };
  assignee: Ref | null;
  incident: Ref | null;
  affectedUsers: number | null;
  createdAt: string;
  updatedAt: string;
  resolvedAt: string | null;
  closedAt: string | null;
  dueAt: string | null;
  isOverdue: boolean;
};

export type TicketNote = { id: string; author: string; body: string | null; from: TicketStatus | null; to: TicketStatus | null; createdAt: string };
export type TicketDetail = Ticket & { notes: TicketNote[] };

// ---- Incidents ----

export type IncidentKind = "disruption" | "application" | "performance" | "security";
export type IncidentSeverity = "critical" | "major" | "minor";
export type IncidentStatus = "investigating" | "identified" | "monitoring" | "resolved";

export type Incident = {
  id: string;
  number: string;
  title: string;
  kind: IncidentKind;
  severity: IncidentSeverity;
  status: IncidentStatus;
  isActive: boolean;
  application: Ref | null;
  lead: Ref | null;
  companies: Ref[];
  summary: string | null;
  startedAt: string;
  resolvedAt: string | null;
  createdBy: string;
  ticketCount?: number;
};

export type IncidentDetail = Incident & {
  updates: { id: string; status: IncidentStatus; body: string; author: string; createdAt: string }[];
  tickets: { id: string; number: string; title: string; status: TicketStatus; severity: Severity }[];
};

// ---- Monitoring ----

export type HealthReport = {
  overall: "operational" | "degraded" | "down";
  checkedAt: string | null;
  staleSeconds: number;
  platformApi: { status: "operational" | "degraded"; failedPercent: number; averageMs: number | null };
  database: { status: Health } & Partial<Check>;
  applications: { id: string; key: string; name: string; status: Health; statusNote: string | null; uptime: number | null; lastCheck: Check | null; monitored: boolean }[];
  integrations: { id: string; name: string; applicationName: string; target: string | null; status: Integration["status"]; monitored: boolean; lastCheck: Check | null }[];
};

export type TrafficSummary = {
  requestsPerMinute: number;
  requests: number;
  refused: number;
  failed: number;
  failedPercent: number;
  averageMs: number | null;
  slowestMs: number | null;
  activeSessions: number;
};

export type Traffic = {
  hours: number;
  minutesPerBar: number;
  summary: TrafficSummary;
  series: { at: string; requests: number; refused: number; failed: number; averageMs: number | null }[];
  applicationResponse: { id: string; name: string; ms: number | null; status: Health }[];
};

// ---- Activity ----

export type AuditCategory = "admin" | "security" | "support" | "system";

export type AuditEntry = {
  id: string;
  at: string;
  actor: string;
  actorId: string | null;
  action: string;
  category: AuditCategory;
  targetType: string | null;
  targetId: string | null;
  target: string;
  fields: string[];
  companyId: string | null;
  applicationId: string | null;
  address: string | null;
};

// ---- Communications ----

export type NoticeKind = "announcement" | "notification" | "maintenance";
export type NoticeLevel = "info" | "warning" | "critical";
export type NoticeState = "draft" | "scheduled" | "showing" | "ended";

export type Notice = {
  id: string;
  kind: NoticeKind;
  level: NoticeLevel;
  title: string;
  body: string | null;
  company: Ref | null;
  application: Ref | null;
  startsAt: string;
  endsAt: string | null;
  publishedAt: string | null;
  state: NoticeState;
  createdBy: string;
  updatedAt: string;
};

// ---- Settings ----

export type PlatformSettings = {
  platform: { name: string; supportEmail: string | null; timezone: string };
  monitoring: { staleSeconds: number; timeoutSeconds: number; slowMs: number; keepDays: number };
  notifications: { responseHours: Record<Severity, number>; bannerSeverity: IncidentSeverity };
  security: { sessionHours: number; loginAttempts: number; lockoutMinutes: number };
};

// ---- Dashboard ----

export type Dashboard = {
  counts: {
    companies: number;
    activeCompanies: number;
    users: number;
    activeUsers: number;
    applications: number;
    openTickets: number;
    activeIncidents: number;
    pendingRequests: number;
  };
  health: HealthReport;
  traffic: TrafficSummary;
  support: { criticalBugs: number; bugs: number; complaints: number; issues: number; features: number; support: number; unassigned: number; overdue: number };
  overdue: Ticket[];
  incidents: Incident[];
  notices: Notice[];
  recent: AuditEntry[];
};

/** The short lists pickers need. */
export type Options = {
  companies: (Ref & { status: Company["status"] })[];
  applications: (Ref & { key: string })[];
  staff: Ref[];
  incidents: Ref[];
  now: string;
};

/** /auth/me's platform part: which kind of staff is signed in. */
export type StaffMe = { platformRole: Staff["role"]; platformRoleName: string; canAdminister: boolean };
