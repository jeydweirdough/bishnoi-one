import "server-only";
import { accountSend } from "@/src/platform/lib/account";
import type { PeriodKey } from "./periods";

// The Admin Console Home's figures (Platform GET /identity/company/overview), for the page and its Export.

type Counts = { signedIn: number; failed: number; added: number };

export type Overview = {
  people: { active: number; off: number; inBin: number; administrators: number; noRole: number; noApps: number };
  signIns: { today: number; week: number; month: number; never: number; invitesPending: number; passwordsToChange: number };
  security: {
    twoStepAdministrators: { on: number; of: number };
    twoStepEveryone: { on: number; of: number };
    required: boolean;
    failedThisWeek: number;
    lockedNow: number;
    offDomain: number;
  };
  apps: { key: string; name: string; people: number }[];
  roles: { id: string; name: string; people: number }[];
  recent: { id: string; at: string; actor: string; action: string; target: string }[];
  /** The period picked, and the same counts for the period just before it (the cards' up and down). */
  period: { key: PeriodKey; days: number; now: Counts; before: Counts };
  /** The past twelve months, oldest first ("2026-10"), for the chart. */
  months: ({ month: string } & Counts)[];
  administrators: { id: string; name: string; email: string; twoStep: boolean; lastSignIn: string | null }[];
};

const NONE: Counts = { signedIn: 0, failed: 0, added: 0 };

export const EMPTY_OVERVIEW: Overview = {
  people: { active: 0, off: 0, inBin: 0, administrators: 0, noRole: 0, noApps: 0 },
  signIns: { today: 0, week: 0, month: 0, never: 0, invitesPending: 0, passwordsToChange: 0 },
  security: { twoStepAdministrators: { on: 0, of: 0 }, twoStepEveryone: { on: 0, of: 0 }, required: false, failedThisWeek: 0, lockedNow: 0, offDomain: 0 },
  apps: [],
  roles: [],
  recent: [],
  period: { key: "month", days: 30, now: NONE, before: NONE },
  months: [],
  administrators: [],
};

export const loadOverview = (period: PeriodKey) => accountSend<Overview>("GET", `/identity/company/overview?period=${period}`);
