import { redirect } from "next/navigation";
import { query } from "@/src/modules/crm/screens/performance-settings";

export default async function Moved({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  redirect(`/crm/performance${await query(searchParams)}`);
}
