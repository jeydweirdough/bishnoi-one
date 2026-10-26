import "server-only";
import { sendToErrorPage } from "./fail";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import { moduleByKey, type ModuleDef, type ModuleKey } from "./modules";
import { ACCOUNT_COOKIE, COMPANY_COOKIE, COMPANY_HEADER, MODULE_HEADER, VIEW_AS_HEADER, moduleCookie, viewAsCookie } from "./session-cookie";
import type { Me, Org } from "./types";

// The browser never talks to the API. Pages and server actions call it from
// the Next server with the token kept in an httpOnly cookie, so the token
// never reaches browser scripts.
//
// One app, eight APIs (decided 2026-10-23): a request is for the module its
// path belongs to (the proxy sets MODULE_HEADER from the path, never the
// browser), so `api.get("/deals")` on a /crm page goes to the CRM's API with
// the CRM session, and module code needs no change. `apiFor("finance")` names
// another module's API outright.

// Each module's API address, as the Platform's Applications says (decided
// 2026-10-27): so this site needs only PLATFORM_API_URL. Asked again as often
// as the Platform says; while it can't be reached, the last answer stands.
let addresses: { apis: Record<string, string>; until: number } | null = null;

async function addressesOnPlatform(): Promise<Record<string, string>> {
  if (addresses && addresses.until > Date.now()) return addresses.apis;
  const platform = (process.env.PLATFORM_API_URL || "http://127.0.0.1:8305").replace(/\/$/, "");
  try {
    const r = await fetch(`${platform}/public/applications`, { cache: "no-store", signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      const body = (await r.json()) as { apis?: Record<string, string>; askAgainIn?: number };
      addresses = { apis: body.apis ?? {}, until: Date.now() + (body.askAgainIn ?? 300) * 1000 };
      return addresses.apis;
    }
  } catch {
    // Not answering yet: the last answer, or this computer's addresses, until the next try.
  }
  addresses = { apis: addresses?.apis ?? {}, until: Date.now() + 30_000 };
  return addresses.apis;
}

/** A module's API address: its setting (CRM_API_URL...) when set, else the Platform's Applications, else the one on this computer. */
export async function moduleApi(m: ModuleDef): Promise<string> {
  const set = process.env[m.apiEnv];
  if (set || m.accountOnly) return (set || m.apiLocal).replace(/\/$/, "");
  return ((await addressesOnPlatform())[m.appKey] || m.apiLocal).replace(/\/$/, "");
}

/** The module this request is for (from its path, via the proxy), or null outside any module. */
export async function currentModule(): Promise<ModuleDef | null> {
  return moduleByKey((await headers()).get(MODULE_HEADER));
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `API error ${status}`);
  }
}

/**
 * Who is asking, for the API's per-address limits on sign-in. It's what the
 * reverse proxy in front of this server says; in production that proxy must
 * overwrite X-Forwarded-For, or a browser could claim any address.
 */
async function clientAddress(): Promise<string | null> {
  const incoming = await headers();
  return incoming.get("x-forwarded-for")?.split(",")[0].trim() || incoming.get("x-real-ip") || null;
}

type Extra = Record<string, string>;

async function send(method: string, path: string, body?: unknown, extra: Extra = {}, named?: ModuleDef): Promise<Response> {
  const [jar, address, here] = await Promise.all([cookies(), clientAddress(), named ? Promise.resolve(named) : currentModule()]);
  if (!here) throw new ApiError(500, "This page isn't part of a module, so there's no API to ask.");
  const API_URL = await moduleApi(here);
  // A module on the Bishnoi One account itself (the Admin Console) asks with the account's own sign-in.
  const token = jar.get(here.accountOnly ? ACCOUNT_COOKIE : moduleCookie(here.key))?.value;
  // Before signing in, which company: the one last signed in to here. Signed
  // in, the token says (it starts with the company), so nothing is added.
  const company = token ? undefined : jar.get(COMPANY_COOKIE)?.value;
  // An administrator viewing this module as someone: every request answered as them, read-only (src/one/view-as.tsx).
  const viewAs = here.accountOnly ? undefined : jar.get(viewAsCookie(here.key))?.value?.split("|")[0];
  // FormData (a file upload) sets its own multipart Content-Type; everything else is JSON.
  const form = body instanceof FormData;
  try {
    return await fetch(`${API_URL}${path}`, {
      method,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(address ? { "X-Forwarded-For": address } : {}),
        ...(company ? { [COMPANY_HEADER]: company } : {}),
        ...(viewAs ? { [VIEW_AS_HEADER]: viewAs } : {}),
        ...(body === undefined || form ? {} : { "Content-Type": "application/json" }),
        ...extra,
      },
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new ApiError(503, "Can't reach the server just now. Try again in a moment.");
  }
}

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// A restart or a network blip shouldn't cost someone their page. Reads are safe
// to ask for twice; saves never are, so they're never retried.
const BLIPS = new Set([502, 503, 504]);

async function sendThroughBlips(method: string, path: string, body?: unknown, extra?: Extra, named?: ModuleDef): Promise<Response> {
  if (method !== "GET") return send(method, path, body, extra, named);
  try {
    const response = await send(method, path, body, extra, named);
    if (!BLIPS.has(response.status)) return response;
  } catch {
    // unreachable for a moment: fall through and try once more
  }
  await pause(300);
  return send(method, path, body, extra, named);
}

// Over the API's rate limit, the request waits its turn instead of failing: a
// 429 means the API refused it before doing anything, so sending it again is
// safe for saves too. A wait longer than this goes back to the person, worded.
const LONGEST_WAIT_MS = 5000;

async function sendWithRetry(method: string, path: string, body?: unknown, extra?: Extra, named?: ModuleDef): Promise<Response> {
  const response = await sendThroughBlips(method, path, body, extra, named);
  if (response.status !== 429) return response;
  const wait = Number(response.headers.get("retry-after") ?? "1") * 1000;
  if (!(wait > 0 && wait <= LONGEST_WAIT_MS)) return response;
  await response.body?.cancel(); // let the connection go back to the pool
  await pause(wait);
  return sendThroughBlips(method, path, body, extra, named);
}

async function call<T>(method: string, path: string, body?: unknown, extra?: Extra, named?: ModuleDef): Promise<T> {
  const response = await sendWithRetry(method, path, body, extra, named);
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data?.detail ?? response.statusText);
  return data as T;
}

function client(named?: ModuleDef) {
  return {
    get: <T>(path: string, extra?: Extra) => call<T>("GET", path, undefined, extra, named),
    post: <T>(path: string, body?: unknown, extra?: Extra) => call<T>("POST", path, body ?? {}, extra, named),
    patch: <T>(path: string, body: unknown) => call<T>("PATCH", path, body, undefined, named),
    put: <T>(path: string, body: unknown) => call<T>("PUT", path, body, undefined, named),
    del: <T = void>(path: string) => call<T>("DELETE", path, undefined, undefined, named),
    upload: <T>(path: string, form: FormData, method: "POST" | "PUT" = "POST") => call<T>(method, path, form, undefined, named),
  };
}

/** This request's module's API (from the page's path). */
export const api = client();

/** Another module's API, named: apiFor("finance").get("/finance/invoices"). Its session comes from the same account. */
export function apiFor(key: ModuleKey) {
  const m = moduleByKey(key);
  if (!m) throw new Error(`No module ${key}.`);
  return client(m);
}

/** For route handlers that pass a file through: the API's response untouched, or an ApiError. */
export async function fetchFile(path: string): Promise<Response> {
  const response = await sendWithRetry("GET", path);
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data?.detail ?? response.statusText);
  }
  return response;
}

/** For pages: fetch, sending people to sign-in on 401 and to the 404 page on 404. */
export async function load<T>(path: string): Promise<T> {
  try {
    return await api.get<T>(path);
  } catch (error) {
    if (error instanceof ApiError) sendToErrorPage(error.status);
    throw error;
  }
}

// --- GraphQL: what a page reads, in one request (the API's app/graphql_api.py) ---------------
// The rule: a page's reads come through GraphQL; saving, sign-in, files and
// app-to-app calls stay REST (the `api` above).

export type GraphQLError = { message: string; path?: (string | number)[]; extensions?: { code?: string; status?: number } };

/** One query: its data, and the errors of any field that couldn't be read (the rest still comes). */
export async function query<T>(document: string, variables?: Record<string, unknown>): Promise<{ data: T; errors: GraphQLError[] }> {
  let res: { data: T | null; errors?: GraphQLError[] };
  try {
    res = await api.post<{ data: T | null; errors?: GraphQLError[] }>("/graphql", { query: document, variables: variables ?? {} });
  } catch (error) {
    if (error instanceof ApiError) sendToErrorPage(error.status);
    throw error;
  }
  const errors = res.errors ?? [];
  if (errors.some((e) => e.extensions?.code === "UNAUTHENTICATED")) redirect("/auth/renew");
  if (!res.data) throw new ApiError(500, errors[0]?.message ?? "The page couldn't be read.");
  return { data: res.data, errors };
}

/**
 * For pages, as `load` is for REST: the query's data, where each of `needed`
 * must have come back. One that's not found or out of reach shows the 404
 * page; any other failure shows the error page. The other fields may be null
 * (a section the person can't see), and the page leaves those out.
 */
export async function loadQuery<T extends Record<string, unknown>>(document: string, variables: Record<string, unknown> = {}, needed: (keyof T & string)[] = []): Promise<T> {
  const { data, errors } = await query<T>(document, variables);
  for (const key of needed) {
    if (data[key] != null) continue;
    const why = errors.find((e) => e.path?.[0] === key);
    sendToErrorPage(why?.extensions?.status);
    throw new ApiError(why?.extensions?.status ?? 500, why?.message ?? `The page couldn't read ${key}.`);
  }
  return data;
}

/**
 * Every page's frame in one request: who is signed in (with what they can
 * reach) and the menu's red counts. Cached for the whole render, so the
 * layout and the page share it.
 */
export const getFrame = cache(async (): Promise<{ me: Me; unset: Record<string, number> | null }> => {
  const { data } = await query<{ me: Me | null; unset: Record<string, number> | null }>("query Frame { me unset }");
  // A count that can't be had is left out rather than stopping the page; who you are can't be.
  if (!data.me) return { me: await load<Me>("/auth/me"), unset: data.unset };
  return { me: data.me, unset: data.unset };
});

/** Who is signed in and what they can reach. Fetched once per request, however many layouts ask. */
export const getMe = cache(async () => (await getFrame()).me);

/**
 * `getMe()` for a page that belongs to a company.
 *
 * A Developer Admin signs in to the platform, which is in no company, so
 * `me.org` is null until they open one. Rather than every company page carrying
 * a null check for a case that means "you are in the wrong place", they ask for
 * this and a platform session is sent to pick a company.
 */
export async function getCompanyMe(): Promise<Me & { org: Org }> {
  const me = await getMe();
  // The companies list is the Platform app's. Only the shell serves it at
  // "/platform", so this asks where it actually is rather than sending a
  // module app to a path it has never had.
  if (me.org === null) redirect("/");
  return me as Me & { org: Org };
}

export const enc = encodeURIComponent;
