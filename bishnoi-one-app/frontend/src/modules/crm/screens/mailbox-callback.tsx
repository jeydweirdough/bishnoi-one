import Link from "next/link";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { api } from "@/src/platform/lib/api";
import { attempt } from "@/src/platform/lib/result";
import type { MailboxInfo } from "@/src/modules/crm/actions/mailbox";

export const metadata = { title: "Mailbox" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

/** Back from the provider's sign-in: the CRM keeps the mailbox, then says so. */
export default async function MailboxCallbackPage({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const [code, state, refused] = [one(params.code), one(params.state), one(params.error)];
  const r = code && state ? await attempt(() => api.post<MailboxInfo>("/mailbox/finish", { code, state })) : null;
  // The one just connected: the latest.
  const address = r?.ok ? [...r.data.mailboxes].sort((a, b) => b.connectedAt.localeCompare(a.connectedAt))[0]?.address : null;
  return (
    <>
      <PageHeader title="Mailbox" crumbs={[{ href: "/crm/account/mailbox", label: "Mailbox" }]} />
      <Sheet className="max-w-xl px-5 py-6">
        {address ? (
          <p className="text-ink">
            Connected: emails you send from the CRM now go out from <b>{address}</b>.
          </p>
        ) : (
          <p className="text-ink">
            {refused ? "The sign-in was cancelled, so nothing was connected." : (r && !r.ok && r.error) || "Nothing came back from the provider."}
          </p>
        )}
        <Link href="/crm/account/mailbox" className="mt-4 inline-block text-ink underline">
          Back to Mailbox
        </Link>
      </Sheet>
    </>
  );
}
