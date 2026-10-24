// Follow-ups are the To do list in Activities now: the old address goes there.
import { redirect } from "next/navigation";

export default async function Page({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { who } = await searchParams;
  redirect(who === "team" ? "/crm/activities?who=team" : "/crm/activities");
}
