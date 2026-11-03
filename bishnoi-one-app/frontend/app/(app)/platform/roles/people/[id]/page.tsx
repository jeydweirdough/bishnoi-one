// A person opens in the panel beside People now (2026-10-31): this address lands there.
import { redirect } from "next/navigation";

export default async function Person({ params }: { params: Promise<{ id: string }> }) {
  redirect(`/platform/roles/people?person=${encodeURIComponent((await params).id)}`);
}
