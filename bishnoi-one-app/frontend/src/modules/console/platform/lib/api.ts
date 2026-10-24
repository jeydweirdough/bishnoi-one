import "server-only";
import { redirect } from "next/navigation";
import { cache } from "react";
import { load, query } from "@/src/platform/lib/api";
import type { Me, Org } from "./types";

// Platform console's own way of asking who is signed in (as its app had it), over the one
// app's API client, which talks to this module's API with this module's session
// (src/platform/lib/api.ts). Written by scripts/move-module.mjs; decided 2026-10-23.
export { api, apiFor, ApiError, currentModule, enc, fetchFile, load, loadQuery, moduleApi, query, type GraphQLError } from "@/src/platform/lib/api";
export { SESSION_COOKIE } from "./session-cookie";



/** Around every signed-in page: who is signed in, the banner's incidents, what isn't set up. One request (GET /platform/frame), once per page. */
export type Frame = { me: Me; banner: { incidents: unknown[] }; unset: Record<string, number> };


export const getFrame = cache(() => load<Frame>("/platform/frame"));



/** Who is signed in and what they can reach: from the frame, so it costs no request of its own. */
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
  if (me.org === null) {
    redirect("/");
  }
  return me as Me & { org: Org };
}
