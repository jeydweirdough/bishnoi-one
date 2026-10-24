import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { ActivityItem } from "@/src/platform/lib/types";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import type { MailboxInfo } from "@/src/modules/crm/actions/mailbox";
import { EmailPage } from "@/src/modules/crm/components/mailbox/email-page";

export const metadata = { title: "Email" };

/** Email in the CRM: write to customers through your own mailbox's provider, and see what's been sent. */
export default async function EmailScreen() {
  const me = await getCompanyMe();
  if (!can(me, "activities.create")) return <NoAccess what="sending email" />;
  const [box, sent] = await Promise.all([load<MailboxInfo>("/mailbox"), load<{ items: ActivityItem[]; total: number }>("/emails?who=me&limit=50")]);
  const fmt = makeFormat(me.org);
  return (
    <>
      <PageHeader title="Email">
        Write to customers from here. Each email goes out through the provider of the mailbox you pick (Zoho Mail, Gmail, Outlook, or any by SMTP) and is kept on the customer&apos;s page.
      </PageHeader>
      <EmailPage box={box} initial={sent} teamWide={me.role?.scope !== "own"} when={Object.fromEntries(sent.items.map((a) => [a.id, fmt.whenLabel(a.at)]))} />
    </>
  );
}
