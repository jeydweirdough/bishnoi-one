"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// Saved views (benchmark E2): a list's filters kept by name. The API checks who
// may see the list, who may share, and that only a view's owner changes it.

export type ViewList = "companies" | "contacts" | "deals" | "quotes" | "activities";

export type SavedView = {
  id: string;
  list: ViewList;
  name: string;
  query: string;
  shared: boolean;
  mine: boolean;
  owner: { id: string; name: string | null };
  canEdit: boolean;
  updatedAt: string;
};

export type Views = { items: SavedView[]; canShare: boolean };

export async function saveView(input: { list: ViewList; name: string; query: string; shared: boolean }): Promise<Result<SavedView>> {
  return attempt(async () => {
    const v = await api.post<SavedView>("/views", input);
    refresh();
    return v;
  });
}

export async function changeView(id: string, input: { name?: string; query?: string; shared?: boolean }): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/views/${enc(id)}`, input);
    refresh();
    return null;
  });
}

export async function deleteView(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/views/${enc(id)}`);
    refresh();
    return null;
  });
}
