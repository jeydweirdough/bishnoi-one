"use server";

import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// Whether each division's customers show to the other divisions (the API's app/routers/sharing.py).

export type Sharing = { id: string; name: string; shareCustomers: boolean };

/** The divisions this person sets it for: every one for the administrator, the ones they manage for a manager. */
export async function customerSharing(): Promise<Sharing[]> {
  return api.get<Sharing[]>("/customer-sharing").catch(() => []);
}

export async function setCustomerSharing(teamId: string, share: boolean): Promise<Result<Sharing>> {
  return attempt(() => api.put<Sharing>(`/customer-sharing/${enc(teamId)}`, { shareCustomers: share }));
}
