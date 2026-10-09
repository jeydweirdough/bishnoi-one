import { redirect } from "next/navigation";
import { query } from "../../../src/screens/performance-settings";

export default async function Moved({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  redirect(`/performance${await query(searchParams)}`);
}
