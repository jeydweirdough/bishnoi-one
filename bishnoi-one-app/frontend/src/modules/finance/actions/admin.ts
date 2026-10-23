"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";

type Json = Record<string, unknown>;

async function send<T = Json>(
  method: "post" | "put" | "patch" | "del",
  path: string,
  body?: unknown,
): Promise<Result<T>> {
  return attempt(async () => {
    const out = method === "del" ? await api.del<T>(path) : await api[method]<T>(path, body ?? {});
    refresh();
    return out;
  });
}

type Id = { id: string };

// --- users & accounts --------------------------------------------------------

export async function saveUser(id: string | null, input: Json): Promise<Result<unknown>> {
  return id ? send("patch", `/admin/users/${enc(id)}`, input) : send("post", "/admin/users", input);
}

export async function setUserPassword(id: string, password: string): Promise<Result<unknown>> {
  return attempt(async () => {
    await api.post(`/admin/users/${enc(id)}/password`, { password });
    return {};
  });
}

// --- roles & permissions -----------------------------------------------------

export async function saveRole(id: string | null, input: Json): Promise<Result<Id & { name: string }>> {
  return id ? send("patch", `/admin/roles/${enc(id)}`, input) : send("post", "/admin/roles", input);
}

export async function deleteRole(id: string): Promise<Result<null>> {
  return send<null>("del", `/admin/roles/${enc(id)}`);
}

