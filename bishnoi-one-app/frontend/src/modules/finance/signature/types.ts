// E-signatures, as the API sends them (app/signatures.py; GET /auth/signature,
// GET /finance/signatures/{record}/{id}). Decided 2026-10-22.

export type MySignature = {
  current: { method: "drawn" | "uploaded"; setAt: string; image: string } | null;
  /** How a change is confirmed: the Finance password, or (Bishnoi One sign-in) a recent sign-in. */
  confirmBy: "password" | "recent_sign_in";
  recentSignIn: boolean;
};

/** One signed step on a document, with the signature it was signed with (none if unset then). */
export type SignedStep = { step: string; label: string; name: string; role: string; at: string; image: string | null; ref: string };
