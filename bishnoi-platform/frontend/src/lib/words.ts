// The platform's words for its codes, in one place so every screen says the same.

import type {
  AuditCategory,
  AuditEntry,
  Health,
  IncidentKind,
  IncidentSeverity,
  IncidentStatus,
  NoticeKind,
  NoticeState,
  Severity,
  TicketKind,
  TicketStatus,
} from "./types";

export const HEALTH: Record<Health, string> = {
  operational: "Operational",
  degraded: "Degraded",
  down: "Down",
  maintenance: "Maintenance",
  unknown: "Not checked",
  retired: "Retired",
};

export const TICKET_KINDS: Record<TicketKind, { one: string; many: string; what: string }> = {
  complaint: { one: "Complaint", many: "Complaints", what: "Somebody is unhappy with how something works for them." },
  bug: { one: "Bug", many: "Bug reports", what: "Something that should work doesn't." },
  issue: { one: "System issue", many: "System issues", what: "Something wrong behind the scenes: a sync, a job, a slowdown." },
  feature: { one: "Feature request", many: "Feature requests", what: "Something that doesn't exist yet." },
  support: { one: "Support ticket", many: "Support tickets", what: "A question, or a hand needed." },
};

/** In lifecycle order. */
export const TICKET_STATUSES: Record<TicketStatus, string> = {
  reported: "Reported",
  triaged: "Triaged",
  assigned: "Assigned",
  investigating: "Investigating",
  fixing: "Fix in development",
  testing: "Testing",
  resolved: "Resolved",
  closed: "Closed",
};

export const SEVERITIES: Record<Severity, string> = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };

export const INCIDENT_KINDS: Record<IncidentKind, string> = {
  disruption: "Service disruption",
  application: "Application issue",
  performance: "Performance issue",
  security: "Security",
};

export const INCIDENT_SEVERITIES: Record<IncidentSeverity, string> = { critical: "Critical", major: "Major", minor: "Minor" };

/** In order. */
export const INCIDENT_STATUSES: Record<IncidentStatus, { label: string; what: string }> = {
  investigating: { label: "Investigating", what: "Something is wrong; the cause isn't known yet." },
  identified: { label: "Identified", what: "The cause is known and a fix is under way." },
  monitoring: { label: "Monitoring", what: "A fix is in; watching that it holds." },
  resolved: { label: "Resolved", what: "Over." },
};

export const NOTICE_KINDS: Record<NoticeKind, { one: string; many: string }> = {
  announcement: { one: "Announcement", many: "Announcements" },
  notification: { one: "System notification", many: "System notifications" },
  maintenance: { one: "Maintenance notice", many: "Maintenance notices" },
};

export const NOTICE_STATES: Record<NoticeState, string> = { draft: "Draft", scheduled: "Scheduled", showing: "Active", ended: "Ended" };

export const AUDIT_CATEGORIES: Record<AuditCategory, string> = {
  admin: "Administrative",
  security: "Security",
  support: "Support",
  system: "System",
};

// What an audit line's action says, as a sentence's verb. Unknown actions fall
// back to their code with the dots made spaces.
const ACTIONS: Record<string, string> = {
  "auth.signed_in": "signed in",
  "auth.signed_out": "signed out",
  "auth.sign_in_failed": "failed to sign in",
  "auth.password_changed": "changed their password",
  "auth.session_ended": "ended a session of",
  "staff.created": "created a staff account for",
  "staff.role_changed": "changed the role of",
  "staff.enabled": "activated",
  "staff.disabled": "deactivated",
  "staff.password_reset": "reset the password of",
  "company.created": "added the company",
  "company.updated": "changed the company",
  "company.suspended": "suspended",
  "company.reactivated": "reactivated",
  "company.app_granted": "assigned an application:",
  "company.app_withdrawn": "removed an application:",
  "department.created": "added the department",
  "department.updated": "changed the department",
  "department.deleted": "removed the department",
  "branch.created": "added the branch",
  "branch.updated": "changed the branch",
  "branch.deleted": "removed the branch",
  "application.created": "registered",
  "application.updated": "changed",
  "application.status_declared": "declared the status of",
  "application.deployed": "recorded a deployment of",
  "integration.created": "added the integration",
  "integration.updated": "changed the integration",
  "integration.deleted": "removed the integration",
  "user.created": "added",
  "user.updated": "changed",
  "user.suspended": "suspended",
  "user.reactivated": "reactivated",
  "access.granted": "granted access:",
  "access.changed": "changed access:",
  "access.withdrawn": "revoked access:",
  "access.requested": "submitted an access request:",
  "access.request_approved": "approved access:",
  "access.request_declined": "declined access:",
  "ticket.created": "logged",
  "ticket.updated": "changed",
  "incident.declared": "declared",
  "incident.updated": "changed",
};

export function actionWords(e: Pick<AuditEntry, "action">): string {
  if (ACTIONS[e.action]) return ACTIONS[e.action];
  const [what, verb] = e.action.split(".");
  if (what === "ticket" && verb in TICKET_STATUSES) return `moved to ${TICKET_STATUSES[verb as TicketStatus]}:`;
  if (what === "incident" && verb in INCIDENT_STATUSES) return `marked ${INCIDENT_STATUSES[verb as IncidentStatus].label}:`;
  if (what === "settings") return "changed settings:";
  if (what in NOTICE_KINDS) return `${verb} the ${NOTICE_KINDS[what as NoticeKind].one.toLowerCase()}`;
  return e.action.replace(/[._]/g, " ");
}

/** "3 min ago", "2 h ago", "4 d ago": how long since, in the fewest words. */
export function ago(iso: string | null, now = Date.now()): string {
  if (!iso) return "never";
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

/** A moment, written out in the platform's zone: "Sep 24, 2026, 10:42 AM". */
export function when(iso: string | null, zone = "Asia/Manila"): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-PH", { timeZone: zone, dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n.toLocaleString("en-PH")} ${n === 1 ? one : many}`;
