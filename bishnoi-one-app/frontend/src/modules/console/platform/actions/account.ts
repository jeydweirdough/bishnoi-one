"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/console/platform/lib/api";
import { attempt, type Result } from "@/src/modules/console/platform/lib/result";

// A person's own picture, and an admin setting one for someone in their company.
// The API resizes whatever is sent to a 256px square and drops the camera's data.

export async function saveMyPhoto(form: FormData): Promise<Result> {
  return attempt(async () => {
    await api.upload("/me/photo", form, "PUT");
    refresh();
    return null;
  });
}

export async function removeMyPhoto(): Promise<Result> {
  return attempt(async () => {
    await api.del("/me/photo");
    refresh();
    return null;
  });
}

export async function savePersonPhoto(id: string, form: FormData): Promise<Result> {
  return attempt(async () => {
    await api.upload(`/admin/users/${enc(id)}/photo`, form, "PUT");
    refresh();
    return null;
  });
}

export async function removePersonPhoto(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/users/${enc(id)}/photo`);
    refresh();
    return null;
  });
}

/** What a person keeps about themselves (the API's /auth/profile). */
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
  return attempt(async () => {
    const saved = await api.put<Profile>("/auth/profile", input);
    // The name is everywhere: the sidebar, the top right, every list.
    refresh();
    return saved;
  });
}
