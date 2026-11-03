import { getAccount } from "@/src/platform/lib/account";
import { PlainFrame } from "@/src/one/plain-frame";
import { AssistantChat } from "@/src/one/assistant/chat";
import { PageHeader } from "@/src/platform/ui/sheet";
export const metadata = { title: "Company assistant" };

export default async function AssistantPage() {
  const account = await getAccount();
  return <PlainFrame><main className="mx-auto max-w-5xl px-4 py-6"><PageHeader title="Company assistant" />{account.company ? <AssistantChat key={`${account.id}:${account.company.id}`} companyId={account.company.id} companyName={account.company.name} /> : <p>Select a company before using its assistant.</p>}</main></PlainFrame>;
}
