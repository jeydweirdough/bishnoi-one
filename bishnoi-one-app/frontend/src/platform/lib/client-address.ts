// Who is asking, for the API's per-address limits and sign-in records (backend guard.py).
// Behind Cloudflare, CF-Connecting-IP is the visitor's address, set by Cloudflare itself (a visitor's own
// copy is overwritten), so it's taken first. X-Forwarded-For's first entry can be written by anyone, so
// it's used only where nothing sits in front (this computer); on the server set TRUST_FORWARDED_FOR=false
// once Cloudflare is in front, so an address can't be faked if CF-Connecting-IP is ever missing.

const looksLikeAddress = (s: string) => /^[0-9a-fA-F:.]{2,45}$/.test(s);

export function clientAddressFrom(h: Headers): string | null {
  const cf = h.get("cf-connecting-ip")?.trim();
  if (cf && looksLikeAddress(cf)) return cf;
  if (process.env.TRUST_FORWARDED_FOR === "false") return null;
  const forwarded = h.get("x-forwarded-for")?.split(",")[0].trim() || h.get("x-real-ip")?.trim();
  return forwarded && looksLikeAddress(forwarded) ? forwarded : null;
}
