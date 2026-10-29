import "server-only";
import { cache } from "react";
import { accountSend } from "@/src/platform/lib/account";

// The company's letterhead on every printed document (feature plan step 10): kept on the Platform
// (Admin Console > Company profile > Letterhead) and read here with the person's own sign-in, so each
// module prints with the same name, address, TIN, logo and footer.

export type Letterhead = {
  name: string;
  legalName: string;
  address: string | null;
  tin: string | null;
  phone: string | null;
  email: string | null;
  footer: string | null;
  logo: string | null;
};

/** The company's letterhead, once per request; null when the Platform can't be reached. */
export const loadLetterhead = cache(async (): Promise<Letterhead | null> => {
  try {
    return await accountSend<Letterhead>("GET", "/identity/company/letterhead");
  } catch {
    return null;
  }
});

/** The company block at the top left of a printed document: logo, legal name, address, TIN, contacts. */
export function LetterheadBlock({ head, fallbackName }: { head: Letterhead | null; fallbackName: string }) {
  const contacts = [head?.phone, head?.email].filter(Boolean).join(" · ");
  return (
    <div className="flex items-start gap-3">
      {head?.logo && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={head.logo} alt="" className="h-14 max-w-[40mm] object-contain" />
      )}
      <div>
        <p className="text-[16pt] leading-tight font-bold">{head?.legalName || fallbackName}</p>
        {head?.address && <p className="text-[9pt]">{head.address}</p>}
        {head?.tin && <p className="text-[9pt]">TIN {head.tin}</p>}
        {contacts && <p className="text-[9pt]">{contacts}</p>}
      </div>
    </div>
  );
}

/** The company's own line at the foot of every document, when it set one. */
export function LetterheadFooter({ head }: { head: Letterhead | null }) {
  return head?.footer ? <p className="mb-1">{head.footer}</p> : null;
}
