import { PageHeader } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import type { MailboxInfo } from "@/src/modules/crm/actions/mailbox";
import { MailboxPanel } from "@/src/modules/crm/components/mailbox/mailbox-panel";

export const metadata = { title: "Mailbox" };

/** Account → Mailbox: the person's own mailbox, to send email from the CRM. */
export default async function MailboxPage() {
  const info = await load<MailboxInfo>("/mailbox");
  return (
    <>
      <PageHeader title="Mailbox" crumbs={[{ href: "/crm/account", label: "Account" }]}>
        Connect your own mailbox, so the emails you send from a customer&apos;s page go out from your address and are kept on the customer.
      </PageHeader>
      <MailboxPanel info={info} />
    </>
  );
}
