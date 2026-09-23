import { FinanceTaskList } from "../components/task-list";

export const metadata = { title: "Approvals" };

/**
 * What a module's page takes, written out rather than borrowed from the shell's
 * `{ params: Promise<Record<string, never>>; searchParams: Promise<Record<string, string | string[] | undefined>> }`. The URL belongs to the shell; this only needs to
 * know it is handed a division and possibly a state.
 */
type Props = {
  params: Promise<{ module: string }>;
  searchParams: Promise<{ state?: string | string[] }>;
};

export default async function Page({ params, searchParams }: Props) {
  const { module } = await params;
  const { state } = await searchParams;
  return <FinanceTaskList module={module} task="approvals" state={state === "done" ? "done" : "open"} />;
}
