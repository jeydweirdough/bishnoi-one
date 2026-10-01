import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";
import { api, ApiError } from "../lib/api";

// One sign-in for the apps around Bishnoi One (the Orders app). The app sends the
// browser here; someone not signed in gets the sign-in page first (proxy.ts),
// then comes back. Bishnoi One's API makes a one-time code for this person's
// session, and only for an address registered to that app, and the browser
// goes back with it.

function refuse(message: string, status = 400): Response {
  return new Response(message, { status, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
}

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams;
  const clientId = q.get("client_id");
  const redirectUri = q.get("redirect_uri");
  const challenge = q.get("code_challenge");
  const method = q.get("code_challenge_method") ?? "S256";
  const state = q.get("state");
  if (!clientId || !redirectUri || !challenge || (q.get("response_type") ?? "code") !== "code") {
    return refuse("This sign-in link is incomplete. Go back to the app and try again.");
  }

  let code: { code: string; redirectUri: string };
  try {
    code = await api.post("/sso/codes", { clientId, redirectUri, codeChallenge: challenge, codeChallengeMethod: method });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      const back = `${request.nextUrl.pathname}${request.nextUrl.search}`;
      redirect(`/login?expired=1&next=${encodeURIComponent(back)}`);
    }
    if (error instanceof ApiError && (error.status === 400 || error.status === 422)) {
      return refuse("That app isn't set up to sign in through Bishnoi One. Ask your admin.");
    }
    return refuse("Bishnoi One couldn't sign you in just now. Try again in a minute.", 503);
  }

  // The API only answers with the exact address registered for this app.
  const back = new URL(code.redirectUri);
  back.searchParams.set("code", code.code);
  if (state) back.searchParams.set("state", state);
  redirect(back.toString());
}
