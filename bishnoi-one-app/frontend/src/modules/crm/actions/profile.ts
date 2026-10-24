"use server";

import { revalidatePath } from "next/cache";
import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

/** What a person keeps about themselves (app/routers/profile.py). */
export type Profile = {
  firstName: string;
  middleInitial: string | null;
  lastName: string;
  suffix: string | null;
  gender: "male" | "female" | "other" | null;
  phone: string | null;
  email: string;
  birthday: string | null;
  fullName: string;
};

export type ProfileInput = Omit<Profile, "fullName" | "gender"> & { gender: string; currentPassword?: string };

/** Saves one's own profile; a new email needs `currentPassword`. */
export async function saveProfile(input: ProfileInput): Promise<Result<Profile>> {
  const r = await attempt(() => api.put<Profile>("/auth/profile", input));
  // The name is everywhere: the sidebar, the top right, every list.
  if (r.ok) revalidatePath("/crm", "layout");
  return r;
}
