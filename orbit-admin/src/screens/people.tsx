import { Plus } from "lucide-react";
import Link from "next/link";
import { Avatar } from "@/src/platform/ui/avatar";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { accessLabel } from "@/src/platform/lib/labels";
import type { AdminUser } from "@/src/platform/lib/types";

export const metadata = { title: "People" };

export default async function PeoplePage() {
  const people = await load<AdminUser[]>("/admin/users");
  const active = people.filter((p) => p.isActive).length;

  return (
    <>
      <PageHeader
        title="People"
        actions={
          <LinkButton href="/settings/people/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
            Add person
          </LinkButton>
        }
      >
        {active} active · {people.length - active} switched off. Each person gets one or more roles, each in a module and a team.
      </PageHeader>

      <Sheet>
        {people.length === 0 ? (
          <Empty icon="people" title="No one yet" />
        ) : (
          <ul className="divide-y divide-rule">
            {people.map((p) => (
              <li key={p.id}>
                <Link href={`/settings/people/${p.id}`} className="grid gap-1 px-5 py-3 hover:bg-bench/40 md:grid-cols-[16rem_1fr_auto] md:gap-5">
                  <span className="flex min-w-0 items-center gap-2.5">
                    <Avatar name={p.fullName} id={p.id} photoAt={p.photoAt} size="md" className={p.isActive ? "" : "opacity-60"} />
                    <span className="min-w-0">
                      <span className={`block truncate font-semibold ${p.isActive ? "text-hema" : "text-ink-3"}`}>{p.fullName}</span>
                      <span className="block truncate text-meta text-ink-3">{p.email}</span>
                    </span>
                  </span>
                  <span className="min-w-0 text-meta text-ink-2">
                    {p.assignments.length === 0 ? (
                      <span className="text-ink-3">No access yet</span>
                    ) : (
                      p.assignments.map((a) => (
                        <span key={a.id} className="block truncate">
                          <span className="font-medium text-ink">{a.roleName}</span> · {accessLabel(a)}
                        </span>
                      ))
                    )}
                  </span>
                  <span className="text-meta">
                    {!p.isActive && (
                      <span className="inline-flex h-5 items-center rounded-[2px] border border-rule-strong px-1.5 text-stamp text-ink-3 uppercase">
                        Switched off
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
