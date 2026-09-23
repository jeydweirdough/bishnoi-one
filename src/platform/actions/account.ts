"use server";

import { refresh } from "next/cache";
import { api, enc } from "../lib/api";
import { attempt, type Result } from "../lib/result";

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
