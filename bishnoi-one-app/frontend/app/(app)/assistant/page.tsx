import { PlainFrame } from "@/src/one/plain-frame";
import { PageHeader } from "@/src/platform/ui/sheet";
export const metadata = { title: "Company assistant" };

// Bookmarks open the global widget; there is only one conversation per company.
export default function AssistantPage() {
  return <PlainFrame><main className="mx-auto max-w-5xl px-4 py-6"><PageHeader title="Company assistant">Use the assistant at the bottom-right to ask about people or monthly company figures. You can keep it open while working in any module.</PageHeader></main></PlainFrame>;
}
